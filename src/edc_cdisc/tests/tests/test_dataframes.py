from datetime import datetime
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

from edc_cdisc.odm import (
    ODMClinicalDataSerializer,
    ODMSnapshotSerializer,
    ODMStudySerializer,
    ODMTransactionalSerializer,
    odm_metadata_to_dataframe,
    odm_to_dataframe,
)

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


class TestOdmMetadataToDataframe(TestCase):
    def setUp(self) -> None:
        self.visit_schedule = get_visit_schedule(consent_v1)
        self.xml_bytes = ODMStudySerializer(
            visit_schedule=self.visit_schedule,
        ).to_xml()

    def test_returns_dict_with_expected_keys(self) -> None:
        result = odm_metadata_to_dataframe(self.xml_bytes)
        self.assertEqual(
            set(result.keys()),
            {"study_events", "forms", "item_groups", "items", "code_lists"},
        )

    def test_study_events_has_rows(self) -> None:
        result = odm_metadata_to_dataframe(self.xml_bytes)
        df = result["study_events"]
        self.assertGreater(len(df), 0)
        self.assertIn("OID", df.columns)
        self.assertIn("Type", df.columns)

    def test_forms_has_rows(self) -> None:
        result = odm_metadata_to_dataframe(self.xml_bytes)
        df = result["forms"]
        self.assertGreater(len(df), 0)
        self.assertIn("OID", df.columns)

    def test_items_has_rows(self) -> None:
        result = odm_metadata_to_dataframe(self.xml_bytes)
        df = result["items"]
        self.assertGreater(len(df), 0)
        self.assertIn("DataType", df.columns)

    def test_code_lists_has_rows(self) -> None:
        result = odm_metadata_to_dataframe(self.xml_bytes)
        df = result["code_lists"]
        self.assertGreater(len(df), 0)
        self.assertIn("CodedValue", df.columns)
        self.assertIn("Decode", df.columns)


@override_settings(SITE_ID=10)
@time_machine.travel(datetime(2025, 8, 11, 8, 00, tzinfo=utc_tz))
class TestOdmToDataframe(TestCase):
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

    def test_empty_snapshot_returns_empty_wide(self) -> None:
        xml_bytes = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
            subject_identifiers=["NONEXISTENT"],
        ).to_xml()
        df = odm_to_dataframe(xml_bytes)
        self.assertEqual(len(df), 0)
        self.assertIn("subject", df.columns)

    def test_empty_snapshot_returns_empty_long(self) -> None:
        xml_bytes = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
            subject_identifiers=["NONEXISTENT"],
        ).to_xml()
        df = odm_to_dataframe(xml_bytes, long=True)
        self.assertEqual(len(df), 0)
        self.assertIn("item", df.columns)

    def test_snapshot_wide_format(self) -> None:
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        xml_bytes = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        ).to_xml()
        df = odm_to_dataframe(xml_bytes)
        self.assertGreater(len(df), 0)
        self.assertIn("subject", df.columns)
        self.assertIn("event", df.columns)
        self.assertIn("form", df.columns)

    def test_snapshot_long_format(self) -> None:
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        xml_bytes = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        ).to_xml()
        df = odm_to_dataframe(xml_bytes, long=True)
        self.assertGreater(len(df), 0)
        self.assertIn("item", df.columns)
        self.assertIn("value", df.columns)
        self.assertNotIn("transaction_type", df.columns)

    def test_transactional_includes_transaction_type(self) -> None:
        before_create = get_utcnow()
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        xml_bytes = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=before_create,
        ).to_xml()
        df = odm_to_dataframe(xml_bytes, long=True)
        self.assertGreater(len(df), 0)
        self.assertIn("transaction_type", df.columns)
        self.assertTrue(all(v in ("Insert", "Update") for v in df["transaction_type"]))

    def test_combined_snapshot_wide(self) -> None:
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        xml_bytes = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
        ).to_xml()
        df = odm_to_dataframe(xml_bytes)
        self.assertGreater(len(df), 0)

    def test_combined_snapshot_metadata(self) -> None:
        xml_bytes = ODMSnapshotSerializer(
            visit_schedule=self.visit_schedule,
        ).to_xml()
        result = odm_metadata_to_dataframe(xml_bytes)
        self.assertGreater(len(result["study_events"]), 0)
        self.assertGreater(len(result["forms"]), 0)

    def test_wide_has_one_row_per_subject_event_form(self) -> None:
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        xml_bytes = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        ).to_xml()
        df = odm_to_dataframe(xml_bytes)
        self.assertEqual(len(df), 1)
