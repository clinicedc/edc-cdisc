from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand
from django.core.management.color import color_style
from edc_visit_schedule.site_visit_schedules import site_visit_schedules
from lxml import etree

from edc_cdisc.odm import (
    ODMClinicalDataSerializer,
    ODMSnapshotSerializer,
    ODMStudySerializer,
    ODMTransactionalSerializer,
)

if TYPE_CHECKING:
    from argparse import ArgumentParser

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "odm" / "schema" / "cdisc-odm-1.3.1" / "ODM1-3-1.xsd"
)

ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
NS = {"odm": ODM_NS}

style = color_style()


@dataclass
class _ExportOpts:
    vs_name: str
    schema: etree.XMLSchema | None = None
    output_path: Path | None = None
    extra_kwargs: dict = field(default_factory=dict)


class Command(BaseCommand):
    help = (
        "Validate ODM export for all registered visit schedules. "
        "Runs Metadata, Snapshot, Combined, and Transactional exports, "
        "validates against the ODM 1.3.1 XSD, and reports statistics."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--visit-schedule",
            dest="visit_schedule_name",
            default=None,
            help="Validate a single visit schedule (default: all)",
        )
        parser.add_argument(
            "--since-days",
            dest="since_days",
            type=int,
            default=30,
            help="Transactional export lookback in days (default: 30)",
        )
        parser.add_argument(
            "--output-dir",
            dest="output_dir",
            default=None,
            help="Write XML files to this directory for inspection",
        )
        parser.add_argument(
            "--skip-xsd",
            dest="skip_xsd",
            action="store_true",
            default=False,
            help="Skip XSD validation (just export and report stats)",
        )

    def handle(self, *args: str, **options: str | int | bool | None) -> None:  # noqa: ARG002
        visit_schedule_name = options["visit_schedule_name"]
        since_days: int = options["since_days"]  # type: ignore[assignment]
        output_dir = options["output_dir"]
        skip_xsd: bool = options["skip_xsd"]  # type: ignore[assignment]

        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path = None

        schema = None
        if not skip_xsd:
            schema = self._load_schema()

        visit_schedules = self._get_visit_schedules(visit_schedule_name)
        if not visit_schedules:
            self.stderr.write(style.ERROR("No visit schedules found.\n"))
            sys.exit(1)

        since = datetime.now(tz=UTC) - timedelta(days=since_days)
        total_pass = 0
        total_fail = 0

        for vs_name, visit_schedule in visit_schedules.items():
            self.stdout.write(f"\n{'=' * 60}\n")
            self.stdout.write(f" Visit Schedule: {vs_name}\n")
            self.stdout.write(f"{'=' * 60}\n")

            for label, serializer_cls, extra_kwargs in [
                ("Metadata Export", ODMStudySerializer, {}),
                ("Snapshot Data Export", ODMClinicalDataSerializer, {}),
                ("Combined Snapshot", ODMSnapshotSerializer, {}),
                (
                    "Transactional Data Export",
                    ODMTransactionalSerializer,
                    {"since": since},
                ),
            ]:
                opts = _ExportOpts(
                    vs_name=vs_name,
                    schema=schema,
                    output_path=output_path,
                    extra_kwargs=extra_kwargs,
                )
                passed, failed = self._validate_export(
                    label=label,
                    visit_schedule=visit_schedule,
                    serializer_cls=serializer_cls,
                    opts=opts,
                )
                total_pass += passed
                total_fail += failed

        self.stdout.write(f"\n{'=' * 60}\n")
        self.stdout.write(" Summary\n")
        self.stdout.write(f"{'=' * 60}\n")
        self.stdout.write(f"  Passed: {total_pass}\n")
        self.stdout.write(f"  Failed: {total_fail}\n")

        if total_fail:
            self.stdout.write(style.ERROR(f"\n  FAILED ({total_fail} errors)\n\n"))
            sys.exit(1)
        else:
            self.stdout.write(style.SUCCESS("\n  ALL PASSED\n\n"))

    def _load_schema(self) -> etree.XMLSchema:
        self.stdout.write(f"\nLoading XSD schema from {SCHEMA_PATH} ... ")
        if not SCHEMA_PATH.exists():
            self.stderr.write(style.ERROR(f"NOT FOUND: {SCHEMA_PATH}\n"))
            sys.exit(1)
        schema_doc = etree.parse(str(SCHEMA_PATH))
        schema = etree.XMLSchema(schema_doc)
        self.stdout.write(style.SUCCESS("OK\n"))
        return schema

    def _get_visit_schedules(self, name: str | None) -> dict:
        all_vs = site_visit_schedules.visit_schedules
        if name:
            if name not in all_vs:
                self.stderr.write(
                    style.ERROR(
                        f"Visit schedule '{name}' not found. "
                        f"Available: {', '.join(all_vs.keys())}\n"
                    )
                )
                sys.exit(1)
            return {name: all_vs[name]}
        return dict(all_vs)

    def _validate_export(
        self,
        *,
        label: str,
        visit_schedule: object,
        serializer_cls: type,
        opts: _ExportOpts,
    ) -> tuple[int, int]:
        self.stdout.write(f"\n  {label}\n  {'-' * len(label)}\n")

        try:
            serializer = serializer_cls(visit_schedule=visit_schedule, **opts.extra_kwargs)
            xml_bytes = serializer.to_xml()
        except Exception as e:
            self.stdout.write(style.ERROR(f"    Export FAILED: {e}\n"))
            return 0, 1

        doc = etree.fromstring(xml_bytes)
        stats = self._collect_stats(doc)
        self.stdout.write(f"    XML size: {len(xml_bytes):,} bytes\n")
        for stat_label, value in stats.items():
            self.stdout.write(f"    {stat_label}: {value}\n")

        passed, failed = self._check_xsd(doc, opts.schema)

        if opts.output_path:
            slug = label.lower().replace(" ", "_")
            filename = f"{opts.vs_name}_{slug}.xml"
            filepath = opts.output_path / filename
            filepath.write_bytes(xml_bytes)
            self.stdout.write(f"    Written to: {filepath}\n")

        return passed, failed

    def _check_xsd(
        self, doc: etree._Element, schema: etree.XMLSchema | None
    ) -> tuple[int, int]:
        if schema is None:
            self.stdout.write("    XSD validation: SKIPPED\n")
            return 1, 0
        is_valid = schema.validate(doc)
        if is_valid:
            self.stdout.write(style.SUCCESS("    XSD validation: PASSED\n"))
            return 1, 0
        self.stdout.write(style.ERROR("    XSD validation: FAILED\n"))
        for error in schema.error_log:
            self.stdout.write(style.ERROR(f"      {error}\n"))
        return 0, 1

    @staticmethod
    def _collect_stats(doc: etree._Element) -> dict[str, int | str]:
        stats: dict[str, int | str] = {}

        file_type = doc.get("FileType", "n/a")
        stats["FileType"] = file_type

        studies = doc.findall("odm:Study", NS)
        if studies:
            stats["Study elements"] = len(studies)
            for study in studies:
                mdv = study.find("odm:MetaDataVersion", NS)
                if mdv is not None:
                    stats["StudyEventDefs"] = len(mdv.findall("odm:StudyEventDef", NS))
                    stats["FormDefs"] = len(mdv.findall("odm:FormDef", NS))
                    stats["ItemGroupDefs"] = len(mdv.findall("odm:ItemGroupDef", NS))
                    stats["ItemDefs"] = len(mdv.findall("odm:ItemDef", NS))
                    stats["CodeLists"] = len(mdv.findall("odm:CodeList", NS))

        cds = doc.findall("odm:ClinicalData", NS)
        if cds:
            stats["ClinicalData elements"] = len(cds)
            total_subjects = 0
            total_events = 0
            total_forms = 0
            total_items = 0
            for cd in cds:
                subjects = cd.findall("odm:SubjectData", NS)
                total_subjects += len(subjects)
                for sd in subjects:
                    events = sd.findall("odm:StudyEventData", NS)
                    total_events += len(events)
                    for se in events:
                        forms = se.findall("odm:FormData", NS)
                        total_forms += len(forms)
                        for fd in forms:
                            for ig in fd.findall("odm:ItemGroupData", NS):
                                total_items += len(ig.findall("odm:ItemData", NS))
            stats["Subjects"] = total_subjects
            stats["StudyEvents"] = total_events
            stats["Forms"] = total_forms
            stats["ItemData values"] = total_items

        return stats
