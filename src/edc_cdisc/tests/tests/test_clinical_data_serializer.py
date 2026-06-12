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

from edc_cdisc.odm import ODMClinicalDataSerializer, ODMTransactionalSerializer
from edc_cdisc.odm.clinical_data_builders import serialize_value
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
