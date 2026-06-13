from datetime import UTC, datetime
from pathlib import Path
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
    ODMStudySerializer,
    ODMTransactionalSerializer,
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

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "odm" / "schema" / "cdisc-odm-1.3.1" / "ODM1-3-1.xsd"
)


def get_odm_schema() -> etree.XMLSchema:
    schema_doc = etree.parse(str(SCHEMA_PATH))
    return etree.XMLSchema(schema_doc)


class TestXSDMetadataExport(TestCase):
    """Validate ODMStudySerializer output against the ODM 1.3.1 XSD."""

    def setUp(self) -> None:
        self.visit_schedule = get_visit_schedule(consent_v1)
        self.schema = get_odm_schema()

    def test_schema_loads(self) -> None:
        self.assertIsNotNone(self.schema)

    def test_metadata_export_validates(self) -> None:
        xml_bytes = ODMStudySerializer(
            visit_schedule=self.visit_schedule,
        ).to_xml()
        doc = etree.fromstring(xml_bytes)
        is_valid = self.schema.validate(doc)
        if not is_valid:
            errors = "\n".join(str(e) for e in self.schema.error_log)
            self.fail(f"Metadata export XSD validation failed:\n{errors}")


@override_settings(SITE_ID=10)
@time_machine.travel(datetime(2025, 8, 11, 8, 00, tzinfo=utc_tz))
class TestXSDSnapshotExport(TestCase):
    """Validate ODMClinicalDataSerializer output against the ODM 1.3.1 XSD."""

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
        self.schema = get_odm_schema()

    def test_snapshot_empty_validates(self) -> None:
        """Snapshot with no CRFs submitted."""
        xml_bytes = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
            subject_identifiers=["NONEXISTENT"],
        ).to_xml()
        doc = etree.fromstring(xml_bytes)
        is_valid = self.schema.validate(doc)
        if not is_valid:
            errors = "\n".join(str(e) for e in self.schema.error_log)
            self.fail(f"Snapshot (empty) XSD validation failed:\n{errors}")

    def test_snapshot_with_data_validates(self) -> None:
        """Snapshot with a submitted CRF."""
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        xml_bytes = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
        ).to_xml()
        doc = etree.fromstring(xml_bytes)
        is_valid = self.schema.validate(doc)
        if not is_valid:
            errors = "\n".join(str(e) for e in self.schema.error_log)
            self.fail(f"Snapshot (with data) XSD validation failed:\n{errors}")


@override_settings(SITE_ID=10)
@time_machine.travel(datetime(2025, 8, 11, 8, 00, tzinfo=utc_tz))
class TestXSDTransactionalExport(TestCase):
    """Validate ODMTransactionalSerializer output against the ODM 1.3.1 XSD."""

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
        self.schema = get_odm_schema()

    def test_transactional_empty_validates(self) -> None:
        """Transactional with no changes."""
        far_future = datetime(2099, 1, 1, tzinfo=UTC)
        xml_bytes = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=far_future,
        ).to_xml()
        doc = etree.fromstring(xml_bytes)
        is_valid = self.schema.validate(doc)
        if not is_valid:
            errors = "\n".join(str(e) for e in self.schema.error_log)
            self.fail(f"Transactional (empty) XSD validation failed:\n{errors}")

    def test_transactional_with_insert_validates(self) -> None:
        """Transactional with an inserted CRF."""
        before_create = get_utcnow()
        CrfLongitudinalOne.objects.create(
            subject_visit=self.subject_visit,
            report_datetime=self.subject_visit.report_datetime,
        )
        xml_bytes = ODMTransactionalSerializer(
            visit_schedule=self.visit_schedule,
            since=before_create,
        ).to_xml()
        doc = etree.fromstring(xml_bytes)
        is_valid = self.schema.validate(doc)
        if not is_valid:
            errors = "\n".join(str(e) for e in self.schema.error_log)
            self.fail(f"Transactional (insert) XSD validation failed:\n{errors}")
