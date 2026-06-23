from datetime import datetime
from zoneinfo import ZoneInfo

import time_machine
from clinicedc_tests.consents import consent_v1
from clinicedc_tests.helper import Helper
from clinicedc_tests.models import CrfFour
from dateutil.relativedelta import relativedelta
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
)
from edc_cdisc.utils import is_encrypted_field, validate_odm

NS = {"odm": ODM_NAMESPACE}

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


class TestEncryptedFieldDetection(TestCase):
    def test_is_encrypted_field(self) -> None:
        self.assertTrue(is_encrypted_field(EncryptedCharField()))
        self.assertTrue(is_encrypted_field(FirstnameField()))
        self.assertFalse(is_encrypted_field(models.CharField()))
        self.assertFalse(is_encrypted_field(models.IntegerField()))
