from datetime import datetime
from zoneinfo import ZoneInfo

import time_machine
from clinicedc_tests.consents import consent_v1
from clinicedc_tests.helper import Helper
from clinicedc_tests.models import CrfFour, SubjectConsent, SubjectScreening
from dateutil.relativedelta import relativedelta
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase, override_settings
from django_crypto_fields.fields import EncryptedCharField, FirstnameField
from edc_consent.site_consents import site_consents
from edc_facility.import_holidays import import_holidays
from edc_registration.models import RegisteredSubject
from edc_sites.single_site import SingleSite
from edc_sites.utils import add_or_update_django_sites
from edc_utils import get_utcnow
from edc_visit_schedule.schedule import Schedule
from edc_visit_schedule.site_visit_schedules import site_visit_schedules
from edc_visit_schedule.visit import Crf, CrfCollection, RequisitionCollection, Visit
from edc_visit_schedule.visit_schedule import VisitSchedule
from lxml import etree

from edc_cdisc.constants import ODM_NAMESPACE
from edc_cdisc.serializers import (
    ClinicalDataSerializer,
    MetadataSerializer,
    SnapshotSerializer,
    TransactionalSerializer,
)
from edc_cdisc.serializers.admin_data_mixin import AdminDataMixin
from edc_cdisc.utils import is_encrypted_field, iter_whitelist_fields, validate_odm

CONSENT_OID = "CE.clinicedc_tests.subjectconsent"

NS = {"odm": ODM_NAMESPACE}

# screening model has no admin in clinicedc_tests; register a clean one
# (plain admin → auto fieldsets of real fields; encrypted PII is dropped)
if not admin.site.is_registered(SubjectScreening):

    @admin.register(SubjectScreening)
    class _SubjectScreeningAdmin(admin.ModelAdmin):
        pass


utc_tz = ZoneInfo("UTC")
EDC_MODULE = "edc_cdisc"

DEFAULT_SITES = [
    SingleSite(
        10,
        "mochudi",
        title="Mochudi",
        country="botswana",
        country_code="bw",
        language_codes=["en"],
        domain="mochudi.bw.clinicedc.org",
    ),
]


def get_minimal_visit_schedule(cdef) -> VisitSchedule:
    """A minimal schedule the strict serializer can run against: clean
    admin-backed CRFs (CrfFour/CrfFive), the default missed model
    (now admin-backed), and an abstract death_report_model that
    get_common_models skips.
    """
    crfs = CrfCollection(
        Crf(show_order=1, model="clinicedc_tests.crffour", required=True),
        Crf(show_order=2, model="clinicedc_tests.crffive", required=True),
    )
    visit = Visit(
        code="1000",
        title="Day 1",
        timepoint=0,
        rbase=relativedelta(months=0),
        rlower=relativedelta(days=0),
        rupper=relativedelta(days=6),
        requisitions=RequisitionCollection(),
        crfs=crfs,
        crfs_unscheduled=CrfCollection(),
        crfs_missed=None,  # defaults to settings.SUBJECT_VISIT_MISSED_MODEL
        allow_unscheduled=False,
    )
    schedule = Schedule(
        name="schedule",
        onschedule_model="edc_visit_schedule.onschedule",
        offschedule_model="clinicedc_tests.offschedule",
        consent_definitions=[cdef],
        appointment_model="edc_appointment.appointment",
    )
    schedule.add_visit(visit)
    visit_schedule = VisitSchedule(
        name="visit_schedule",
        offstudy_model="edc_offstudy.subjectoffstudy",
        death_report_model="edc_adverse_event.deathreport",  # abstract → skipped
    )
    visit_schedule.add_schedule(schedule)
    return visit_schedule


@override_settings(SITE_ID=10)
@time_machine.travel(datetime(2025, 8, 11, 8, 0, tzinfo=utc_tz))
class TestValidateOdm(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        import_holidays()
        add_or_update_django_sites(single_sites=DEFAULT_SITES, verbose=False)

    def setUp(self) -> None:
        site_consents.registry = {}
        site_consents.register(consent_v1)
        site_visit_schedules._registry = {}
        site_visit_schedules.loaded = False
        self.visit_schedule = get_minimal_visit_schedule(consent_v1)
        site_visit_schedules.register(self.visit_schedule)
        self.helper = Helper(now=get_utcnow())
        self.subject_visit = self.helper.enroll_to_baseline(
            visit_schedule_name=self.visit_schedule.name,
            schedule_name="schedule",
        )
        CrfFour.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )

    def _build(self, cls) -> bytes:
        return cls(edc_module_name=EDC_MODULE, visit_schedule=self.visit_schedule).to_xml()

    def test_metadata_validates(self) -> None:
        self.assertEqual(validate_odm(self._build(MetadataSerializer)), [])

    def test_clinical_data_is_xsd_valid(self) -> None:
        # data-only: XSD-valid, but refs point at metadata in a separate file,
        # so only assert there are no XSD problems (dangling refs expected).
        problems = validate_odm(self._build(ClinicalDataSerializer))
        self.assertEqual([p for p in problems if p.startswith("XSD")], [])

    def test_combined_snapshot_validates(self) -> None:
        self.assertEqual(validate_odm(self._build(SnapshotSerializer)), [])

    def test_subject_set_driven_by_registered_subject(self) -> None:
        # the enrolled subject (has a visit + CRF) appears, keyed by its id
        root = etree.fromstring(self._build(ClinicalDataSerializer))
        keys = {sd.get("SubjectKey") for sd in root.findall(".//odm:SubjectData", NS)}
        self.assertIn(self.subject_visit.subject_identifier, keys)

    def test_enrolled_subject_without_data_is_pruned(self) -> None:
        # a RegisteredSubject with no visits/common/screening is iterated but
        # produces no SubjectData (build_subject_data returns None)
        RegisteredSubject.objects.create(subject_identifier="999-99-0000-0")
        root = etree.fromstring(self._build(ClinicalDataSerializer))
        keys = {sd.get("SubjectKey") for sd in root.findall(".//odm:SubjectData", NS)}
        self.assertNotIn("999-99-0000-0", keys)
        self.assertIn(self.subject_visit.subject_identifier, keys)

    def test_screening_event_def_has_category_alias(self) -> None:
        root = etree.fromstring(self._build(MetadataSerializer))
        sed = root.find(".//odm:StudyEventDef[@OID='CE.clinicedc_tests.subjectscreening']", NS)
        self.assertIsNotNone(sed)
        self.assertEqual(sed.get("Type"), "Common")
        alias = sed.find("odm:Alias[@Context='clinicedc.event_category']", NS)
        self.assertIsNotNone(alias)
        self.assertEqual(alias.get("Name"), "screening")

    def test_screening_event_data_present(self) -> None:
        # consent back-fills the screening subject_identifier; key it to the
        # enrolled subject so it is exported
        SubjectScreening.objects.all().update(
            subject_identifier=self.subject_visit.subject_identifier
        )
        root = etree.fromstring(self._build(SnapshotSerializer))
        sed = root.find(
            ".//odm:ClinicalData//odm:StudyEventData"
            "[@StudyEventOID='CE.clinicedc_tests.subjectscreening']",
            NS,
        )
        self.assertIsNotNone(sed)
        self.assertEqual(validate_odm(self._build(SnapshotSerializer)), [])

    def test_consent_event_def_is_repeating_with_category_alias(self) -> None:
        root = etree.fromstring(self._build(MetadataSerializer))
        sed = root.find(f".//odm:StudyEventDef[@OID='{CONSENT_OID}']", NS)
        self.assertIsNotNone(sed)
        self.assertEqual(sed.get("Type"), "Common")
        # consent is unique on subject_identifier + version → repeating
        self.assertEqual(sed.get("Repeating"), "Yes")
        alias = sed.find("odm:Alias[@Context='clinicedc.event_category']", NS)
        self.assertIsNotNone(alias)
        self.assertEqual(alias.get("Name"), "consent")

    def test_consent_event_data_present_with_repeat_key(self) -> None:
        # enroll_to_baseline created a consent for the enrolled subject
        root = etree.fromstring(self._build(SnapshotSerializer))
        sed = root.find(
            f".//odm:ClinicalData//odm:StudyEventData[@StudyEventOID='{CONSENT_OID}']", NS
        )
        self.assertIsNotNone(sed)
        # repeat key carries the consent version
        self.assertTrue(sed.get("StudyEventRepeatKey"))
        self.assertEqual(validate_odm(self._build(SnapshotSerializer)), [])

    def test_consent_export_drops_encrypted_pii(self) -> None:
        # only the whitelist is exported; encrypted PII (e.g. first_name) must
        # never appear as an ItemDef or ItemData
        meta = etree.fromstring(self._build(MetadataSerializer))
        data = etree.fromstring(self._build(SnapshotSerializer))
        for root in (meta, data):
            oids = {
                e.get("ItemOID") or e.get("OID")
                for e in root.iter()
                if (e.get("ItemOID") or e.get("OID"))
            }
            self.assertNotIn("I.clinicedc_tests.subjectconsent.first_name", oids)
            self.assertIn("I.clinicedc_tests.subjectconsent.version", oids)

    def _attribute_history_to(self, username: str) -> None:
        get_user_model().objects.create(
            username=username,
            first_name="Amos",
            last_name="Otieno",
            email="amos@example.org",
        )
        # no request user in tests → simple_history history_user is null; the
        # serializer falls back to the un-editable audit username on the row
        CrfFour.history.update(user_modified=username)

    def test_transactional_validates_with_audit_records(self) -> None:
        self._attribute_history_to("amos")
        root = etree.fromstring(self._build(TransactionalSerializer))
        self.assertEqual(root.get("FileType"), "Transactional")
        # a CRF FormData carries a TransactionType and a first-child AuditRecord
        fd = root.find(".//odm:FormData[@FormOID='F.clinicedc_tests.crffour']", NS)
        self.assertIsNotNone(fd)
        self.assertIn(fd.get("TransactionType"), {"Insert", "Update"})
        self.assertEqual(fd[0].tag, f"{{{ODM_NAMESPACE}}}AuditRecord")
        self.assertIsNotNone(fd.find("odm:AuditRecord/odm:DateTimeStamp", NS))
        self.assertEqual(validate_odm(self._build(TransactionalSerializer)), [])

    def test_transactional_admin_data_user_and_location(self) -> None:
        self._attribute_history_to("amos")
        root = etree.fromstring(self._build(TransactionalSerializer))
        user = root.find(".//odm:AdminData/odm:User[@OID='USR.amos']", NS)
        self.assertIsNotNone(user)
        self.assertEqual(user.findtext("odm:LoginName", namespaces=NS), "amos")
        self.assertTrue(user.get("UserType"))  # closed enum; field staff → Other
        loc = root.find(".//odm:AdminData/odm:Location[@OID='LOC.10']", NS)
        self.assertIsNotNone(loc)
        ref = loc.find("odm:MetaDataVersionRef", NS)
        self.assertEqual(ref.get("EffectiveDate"), "2019-08-01")  # study_open_datetime

    def test_transactional_records_insert_then_update(self) -> None:
        crf = CrfFour.objects.get(subject_visit=self.subject_visit)
        crf.save()  # second save → an Update history row
        root = etree.fromstring(self._build(TransactionalSerializer))
        txns = [
            fd.get("TransactionType")
            for fd in root.findall(".//odm:FormData[@FormOID='F.clinicedc_tests.crffour']", NS)
        ]
        self.assertIn("Insert", txns)
        self.assertIn("Update", txns)

    def test_transactional_consent_history_drops_encrypted_pii(self) -> None:
        # the guard applies to historical rows too: historical_subjectconsent
        # holds every column, but only the whitelist is serialized
        root = etree.fromstring(self._build(TransactionalSerializer))
        item_oids = {e.get("ItemOID") for e in root.iter() if e.get("ItemOID")}
        self.assertNotIn("I.clinicedc_tests.subjectconsent.first_name", item_oids)


class TestUserTypeMapping(TestCase):
    def test_defaults_to_other_and_promotes_mapped_role(self) -> None:
        self.assertEqual(AdminDataMixin.user_type_for_roles(["nurse"]), "Other")
        with override_settings(EDC_CDISC_USER_TYPE_BY_ROLE={"sponsor_dm": "Sponsor"}):
            # priority Sponsor > Investigator > Lab when several map
            self.assertEqual(
                AdminDataMixin.user_type_for_roles(["nurse", "sponsor_dm"]), "Sponsor"
            )


class TestConsentWhitelistFloor(TestCase):
    def test_floor_drops_encrypted_field_even_if_whitelisted(self) -> None:
        # first_name is an encrypted PII field; whitelisting it must not export
        # it — it is dropped (with a warning) while real fields pass through
        with self.assertWarns(UserWarning):
            fields = list(
                iter_whitelist_fields(
                    SubjectConsent, ["subject_identifier", "first_name", "version"]
                )
            )
        names = {f.name for f in fields}
        self.assertEqual(names, {"subject_identifier", "version"})


class TestEncryptedFieldDetection(TestCase):
    def test_is_encrypted_field(self) -> None:
        self.assertTrue(is_encrypted_field(EncryptedCharField()))
        self.assertTrue(is_encrypted_field(FirstnameField()))
        self.assertFalse(is_encrypted_field(models.CharField()))
        self.assertFalse(is_encrypted_field(models.IntegerField()))
