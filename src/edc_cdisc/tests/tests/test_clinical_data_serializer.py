from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import time_machine
from clinicedc_tests.consents import consent_v1
from clinicedc_tests.helper import Helper
from clinicedc_tests.models import CrfLongitudinalOne
from clinicedc_tests.visit_schedules.visit_schedule import get_visit_schedule
from django.test import TestCase, override_settings
from edc_consent.site_consents import site_consents
from edc_facility.import_holidays import import_holidays
from edc_sites.single_site import SingleSite
from edc_sites.utils import add_or_update_django_sites
from edc_utils import get_utcnow
from edc_visit_schedule.site_visit_schedules import site_visit_schedules
from lxml import etree

from edc_cdisc.odm import (
    ODMClinicalDataSerializer,
    ODMSnapshotSerializer,
    ODMTransactionalSerializer,
)
from edc_cdisc.odm.clinical_data_builders import build_form_data, serialize_value
from edc_cdisc.odm.constants import ODM_NAMESPACE

NS = {"odm": ODM_NAMESPACE}
utc_tz = ZoneInfo("UTC")

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


@override_settings(SITE_ID=10)
@time_machine.travel(datetime(2025, 8, 11, 8, 00, tzinfo=utc_tz))
class TestODMClinicalDataSerializer(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        import_holidays()
        add_or_update_django_sites(single_sites=DEFAULT_SITES, verbose=False)

    def setUp(self) -> None:
        site_consents.registry = {}
        site_consents.register(consent_v1)
        site_visit_schedules._registry = {}
        site_visit_schedules.loaded = False
        self.visit_schedule = get_visit_schedule(consent_v1)
        site_visit_schedules.register(self.visit_schedule)
        self.helper = Helper(now=get_utcnow())
        self.subject_visit = self.helper.enroll_to_baseline(
            visit_schedule_name=self.visit_schedule.name,
            schedule_name="schedule",
        )

    def test_to_xml_returns_bytes(self) -> None:
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        result = serializer.to_xml()
        self.assertIsInstance(result, bytes)

    def test_xml_is_well_formed(self) -> None:
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        self.assertEqual(root.tag, f"{{{ODM_NAMESPACE}}}ODM")

    def test_file_type_snapshot(self) -> None:
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        self.assertEqual(root.get("FileType"), "Snapshot")

    def test_clinical_data_element(self) -> None:
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        cd = root.find("odm:ClinicalData", NS)
        self.assertIsNotNone(cd)
        self.assertIsNotNone(cd.get("StudyOID"))
        self.assertEqual(cd.get("MetaDataVersionOID"), "MDV.1")

    def test_subject_data_element(self) -> None:
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        sds = root.findall("odm:ClinicalData/odm:SubjectData", NS)
        self.assertEqual(len(sds), 1)
        self.assertEqual(
            sds[0].get("SubjectKey"),
            self.subject_visit.subject_identifier,
        )

    def test_subject_data_filter_by_identifier(self) -> None:
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
            subject_identifiers=["NONEXISTENT"],
        )
        root = etree.fromstring(serializer.to_xml())
        sds = root.findall("odm:ClinicalData/odm:SubjectData", NS)
        self.assertEqual(len(sds), 0)

    def test_study_event_data_no_crfs(self) -> None:
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        sed = root.find(
            "odm:ClinicalData/odm:SubjectData/odm:StudyEventData",
            NS,
        )
        self.assertIsNone(sed)

    def test_study_event_data_with_crf(self) -> None:
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        sed = root.find(
            "odm:ClinicalData/odm:SubjectData/odm:StudyEventData",
            NS,
        )
        self.assertIsNotNone(sed)
        self.assertEqual(
            sed.get("StudyEventOID"),
            f"SE.{self.subject_visit.visit_code}",
        )

    def test_form_data_element(self) -> None:
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        fd = root.find(
            "odm:ClinicalData/odm:SubjectData/odm:StudyEventData/odm:FormData",
            NS,
        )
        self.assertIsNotNone(fd)
        self.assertEqual(
            fd.get("FormOID"),
            "F.clinicedc_tests.crflongitudinalone",
        )

    def test_item_data_elements(self) -> None:
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        items = root.findall(
            "odm:ClinicalData/odm:SubjectData"
            "/odm:StudyEventData/odm:FormData"
            "/odm:ItemGroupData/odm:ItemData",
            NS,
        )
        self.assertGreater(len(items), 0)
        for item in items:
            self.assertIsNotNone(item.get("ItemOID"))
            self.assertIsNotNone(item.get("Value"))

    def test_null_field_omitted_by_default(self) -> None:
        crf = CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        crf.f1 = None
        fd = build_form_data("clinicedc_tests.crflongitudinalone", crf)
        oids = [item.get("ItemOID") for item in fd.iter("ItemData")]
        self.assertNotIn("I.clinicedc_tests.crflongitudinalone.f1", oids)

    def test_null_field_emits_isnull_when_included(self) -> None:
        crf = CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        crf.f1 = None
        fd = build_form_data("clinicedc_tests.crflongitudinalone", crf, include_nulls=True)
        f1_items = [
            item
            for item in fd.iter("ItemData")
            if item.get("ItemOID") == "I.clinicedc_tests.crflongitudinalone.f1"
        ]
        self.assertEqual(len(f1_items), 1)
        self.assertEqual(f1_items[0].get("IsNull"), "Yes")
        self.assertIsNone(f1_items[0].get("Value"))

    def test_include_nulls_fixed_item_count(self) -> None:
        """Every form instance emits the same number of ItemData."""
        crf = CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        crf.f1 = None
        with_nulls = build_form_data(
            "clinicedc_tests.crflongitudinalone", crf, include_nulls=True
        )
        crf.f1 = "value"
        all_filled = build_form_data(
            "clinicedc_tests.crflongitudinalone", crf, include_nulls=True
        )
        count_with_null = len(list(with_nulls.iter("ItemData")))
        count_filled = len(list(all_filled.iter("ItemData")))
        self.assertEqual(count_with_null, count_filled)

    def test_meta_path_excludes_audit_fields(self) -> None:
        """Models without a registered admin fall back to the meta path,
        which must not leak audit/system columns.
        """
        crf = CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        fd = build_form_data("clinicedc_tests.crflongitudinalone", crf)
        oids = {item.get("ItemOID") for item in fd.iter("ItemData")}
        prefix = "I.clinicedc_tests.crflongitudinalone."
        for excluded in (
            "created",
            "modified",
            "user_created",
            "user_modified",
            "hostname_created",
            "device_created",
            "locale_created",
            "consent_model",
        ):
            self.assertNotIn(f"{prefix}{excluded}", oids, msg=excluded)

    def test_meta_path_keeps_id_and_action_fields(self) -> None:
        crf = CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        fd = build_form_data("clinicedc_tests.crflongitudinalone", crf)
        oids = {item.get("ItemOID") for item in fd.iter("ItemData")}
        prefix = "I.clinicedc_tests.crflongitudinalone."
        for kept in ("id", "action_identifier", "consent_version", "f1"):
            self.assertIn(f"{prefix}{kept}", oids, msg=kept)

    def test_to_etree_returns_element(self) -> None:
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = serializer.to_etree()
        self.assertIsInstance(root, etree._Element)

    def test_custom_study_oid(self) -> None:
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
            study_oid="S.CUSTOM",
        )
        root = etree.fromstring(serializer.to_xml())
        cd = root.find("odm:ClinicalData", NS)
        self.assertEqual(cd.get("StudyOID"), "S.CUSTOM")

    def test_originator(self) -> None:
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        self.assertEqual(root.get("Originator"), "clinicedc/edc-cdisc")


@override_settings(SITE_ID=10)
@time_machine.travel(datetime(2025, 8, 11, 8, 00, tzinfo=utc_tz))
class TestODMTransactionalSerializer(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        import_holidays()
        add_or_update_django_sites(single_sites=DEFAULT_SITES, verbose=False)

    def setUp(self) -> None:
        site_consents.registry = {}
        site_consents.register(consent_v1)
        site_visit_schedules._registry = {}
        site_visit_schedules.loaded = False
        self.visit_schedule = get_visit_schedule(consent_v1)
        site_visit_schedules.register(self.visit_schedule)
        self.helper = Helper(now=get_utcnow())
        self.subject_visit = self.helper.enroll_to_baseline(
            visit_schedule_name=self.visit_schedule.name,
            schedule_name="schedule",
        )

    def test_file_type_transactional(self) -> None:
        serializer = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=get_utcnow(),
        )
        root = etree.fromstring(serializer.to_xml())
        self.assertEqual(root.get("FileType"), "Transactional")

    def test_to_xml_returns_bytes(self) -> None:
        serializer = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=get_utcnow(),
        )
        self.assertIsInstance(serializer.to_xml(), bytes)

    def test_to_etree_returns_element(self) -> None:
        serializer = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=get_utcnow(),
        )
        self.assertIsInstance(serializer.to_etree(), etree._Element)

    def test_no_changes_since_future(self) -> None:
        """CRF created before `since` and not modified — should not appear."""
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        far_future = datetime(2099, 1, 1, tzinfo=UTC)
        serializer = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=far_future,
        )
        root = etree.fromstring(serializer.to_xml())
        sds = root.findall("odm:ClinicalData/odm:SubjectData", NS)
        self.assertEqual(len(sds), 0)

    def test_insert_transaction_type(self) -> None:
        """CRF created after `since` gets TransactionType=Insert."""
        before_create = get_utcnow()
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        serializer = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=before_create,
        )
        root = etree.fromstring(serializer.to_xml())
        fd = root.find(
            "odm:ClinicalData/odm:SubjectData/odm:StudyEventData/odm:FormData",
            NS,
        )
        self.assertIsNotNone(fd)
        self.assertEqual(fd.get("TransactionType"), "Insert")

    def test_update_transaction_type(self) -> None:
        """CRF created before `since` but modified after gets Update."""
        crf = CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        # Move `since` to after creation
        after_create = get_utcnow()
        # Modify the CRF — save triggers modified update
        crf.save()
        serializer = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=after_create,
        )
        root = etree.fromstring(serializer.to_xml())
        fd = root.find(
            "odm:ClinicalData/odm:SubjectData/odm:StudyEventData/odm:FormData",
            NS,
        )
        self.assertIsNotNone(fd)
        self.assertEqual(fd.get("TransactionType"), "Update")

    def test_snapshot_has_no_transaction_type(self) -> None:
        """Snapshot serializer should NOT have TransactionType."""
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        fd = root.find(
            "odm:ClinicalData/odm:SubjectData/odm:StudyEventData/odm:FormData",
            NS,
        )
        self.assertIsNotNone(fd)
        self.assertIsNone(fd.get("TransactionType"))

    def test_clinical_data_element(self) -> None:
        serializer = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=get_utcnow(),
        )
        root = etree.fromstring(serializer.to_xml())
        cd = root.find("odm:ClinicalData", NS)
        self.assertIsNotNone(cd)
        self.assertIsNotNone(cd.get("StudyOID"))

    def test_item_data_on_insert(self) -> None:
        """Inserted CRF should still carry ItemData values."""
        before_create = get_utcnow()
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        serializer = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=before_create,
        )
        root = etree.fromstring(serializer.to_xml())
        items = root.findall(
            "odm:ClinicalData/odm:SubjectData"
            "/odm:StudyEventData/odm:FormData"
            "/odm:ItemGroupData/odm:ItemData",
            NS,
        )
        self.assertGreater(len(items), 0)

    def test_subject_filter(self) -> None:
        before_create = get_utcnow()
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        serializer = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=before_create,
            subject_identifiers=["NONEXISTENT"],
        )
        root = etree.fromstring(serializer.to_xml())
        sds = root.findall("odm:ClinicalData/odm:SubjectData", NS)
        self.assertEqual(len(sds), 0)


@override_settings(SITE_ID=10)
@time_machine.travel(datetime(2025, 8, 11, 8, 00, tzinfo=utc_tz))
class TestODMSnapshotSerializer(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        import_holidays()
        add_or_update_django_sites(single_sites=DEFAULT_SITES, verbose=False)

    def setUp(self) -> None:
        site_consents.registry = {}
        site_consents.register(consent_v1)
        site_visit_schedules._registry = {}
        site_visit_schedules.loaded = False
        self.visit_schedule = get_visit_schedule(consent_v1)
        site_visit_schedules.register(self.visit_schedule)
        self.helper = Helper(now=get_utcnow())
        self.subject_visit = self.helper.enroll_to_baseline(
            visit_schedule_name=self.visit_schedule.name,
            schedule_name="schedule",
        )

    def test_produces_valid_xml(self) -> None:
        serializer = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
        )
        xml_bytes = serializer.to_xml()
        root = etree.fromstring(xml_bytes)
        self.assertEqual(root.tag, f"{{{ODM_NAMESPACE}}}ODM")

    def test_file_type_is_snapshot(self) -> None:
        serializer = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        self.assertEqual(root.get("FileType"), "Snapshot")

    def test_contains_study_element(self) -> None:
        serializer = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        studies = root.findall("odm:Study", NS)
        self.assertEqual(len(studies), 1)

    def test_contains_clinical_data_element(self) -> None:
        serializer = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        cds = root.findall("odm:ClinicalData", NS)
        self.assertEqual(len(cds), 1)

    def test_study_before_clinical_data(self) -> None:
        serializer = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        children = list(root)
        self.assertEqual(children[0].tag, f"{{{ODM_NAMESPACE}}}Study")
        self.assertEqual(children[1].tag, f"{{{ODM_NAMESPACE}}}ClinicalData")

    def test_study_and_clinical_data_share_oid(self) -> None:
        serializer = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        study_oid = root.find("odm:Study", NS).get("OID")
        cd_oid = root.find("odm:ClinicalData", NS).get("StudyOID")
        self.assertEqual(study_oid, cd_oid)

    def test_clinical_data_has_subject_data(self) -> None:
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        serializer = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = etree.fromstring(serializer.to_xml())
        sds = root.findall("odm:ClinicalData/odm:SubjectData", NS)
        self.assertEqual(len(sds), 1)

    def test_to_etree_returns_element(self) -> None:
        serializer = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
        )
        root = serializer.to_etree()
        self.assertIsInstance(root, etree._Element)
        children = list(root)
        self.assertEqual(len(children), 2)

    def test_subject_filter(self) -> None:
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        serializer = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
            subject_identifiers=["NONEXISTENT"],
        )
        root = etree.fromstring(serializer.to_xml())
        sds = root.findall("odm:ClinicalData/odm:SubjectData", NS)
        self.assertEqual(len(sds), 0)

    def test_metadata_version_oid_matches(self) -> None:
        serializer = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
            metadata_version_oid="MDV.2",
        )
        root = etree.fromstring(serializer.to_xml())
        mdv = root.find("odm:Study/odm:MetaDataVersion", NS)
        cd = root.find("odm:ClinicalData", NS)
        self.assertEqual(mdv.get("OID"), "MDV.2")
        self.assertEqual(cd.get("MetaDataVersionOID"), "MDV.2")


class TestSerializeValue(TestCase):
    def test_none(self) -> None:
        self.assertIsNone(serialize_value(None))

    def test_bool_true(self) -> None:
        self.assertEqual(serialize_value(True), "true")

    def test_bool_false(self) -> None:
        self.assertEqual(serialize_value(False), "false")

    def test_int(self) -> None:
        self.assertEqual(serialize_value(42), "42")

    def test_float(self) -> None:
        self.assertEqual(serialize_value(3.14), "3.14")

    def test_string(self) -> None:
        self.assertEqual(serialize_value("hello"), "hello")

    def test_date(self) -> None:
        self.assertEqual(serialize_value(date(2024, 1, 15)), "2024-01-15")

    def test_datetime(self) -> None:
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        self.assertEqual(serialize_value(dt), "2024-01-15T10:30:00+00:00")

    def test_decimal(self) -> None:
        self.assertEqual(serialize_value(Decimal("1.5")), "1.5")
