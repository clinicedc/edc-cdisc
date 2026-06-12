from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from django.apps import apps as django_apps
from edc_protocol.research_protocol_config import ResearchProtocolConfig
from lxml import etree

from .builders import (
    _iter_crf_fields,
    _model_verbose_name,
    build_code_list,
    build_common_event_def,
    build_form_def,
    build_global_variables,
    build_item_def,
    build_item_group_defs,
    build_protocol,
    build_study_event_def,
    build_unscheduled_event_def,
    collect_common_models,
    collect_unique_models,
    collect_unique_unscheduled_collections,
)
from .constants import ODM_NAMESPACE, ODM_VERSION

if TYPE_CHECKING:
    from edc_visit_schedule.visit_schedule import VisitSchedule


NSMAP = {None: ODM_NAMESPACE}


@dataclass
class ODMStudySerializer:
    visit_schedule: VisitSchedule
    study_oid: str = ""
    study_name: str = ""
    study_description: str = ""
    metadata_version_oid: str = "MDV.1"
    metadata_version_name: str = "Version 1"

    _protocol_config: ResearchProtocolConfig = field(
        init=False, repr=False, default_factory=ResearchProtocolConfig
    )

    def __post_init__(self) -> None:
        if not self.study_oid:
            self.study_oid = f"S.{self._protocol_config.protocol}"
        if not self.study_name:
            self.study_name = self._protocol_config.project_name

    def to_xml(self) -> bytes:
        root = self._build_root()
        study = self._build_study()
        root.append(study)
        return etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    def to_etree(self) -> etree._Element:
        root = self._build_root()
        study = self._build_study()
        root.append(study)
        return root

    def _build_root(self) -> etree._Element:
        now = datetime.now(tz=UTC).isoformat()
        return etree.Element(
            "ODM",
            nsmap=NSMAP,
            FileOID=f"{self.study_oid}.ODM.{now}",
            FileType="Snapshot",
            CreationDateTime=now,
            ODMVersion=ODM_VERSION,
            Originator="clinicedc/edc-cdisc",
        )

    def _build_study(self) -> etree._Element:
        study = etree.Element("Study", OID=self.study_oid)

        study.append(
            build_global_variables(
                protocol_name=self.study_name,
                protocol_title=self._protocol_config.protocol_title,
                study_description=self.study_description,
            )
        )

        mdv = etree.SubElement(
            study,
            "MetaDataVersion",
            OID=self.metadata_version_oid,
            Name=self.metadata_version_name,
        )

        mdv.append(build_protocol(self.visit_schedule))

        for schedule in self.visit_schedule.schedules.values():
            for visit in schedule.visits.values():
                mdv.append(build_study_event_def(visit))

        for name, crfs in collect_unique_unscheduled_collections(self.visit_schedule).items():
            mdv.append(build_unscheduled_event_def(name, crfs))

        for model_label in collect_common_models(self.visit_schedule):
            verbose = _model_verbose_name(model_label)
            mdv.append(build_common_event_def(model_label, verbose))

        self._append_model_definitions(mdv, collect_unique_models(self.visit_schedule))

        return study

    @staticmethod
    def _append_model_definitions(
        mdv: etree._Element,
        models: list[str],
    ) -> None:
        for model_label in models:
            mdv.append(build_form_def(model_label))

        for model_label in models:
            for igd in build_item_group_defs(model_label):
                mdv.append(igd)

        for model_label in models:
            model_cls = django_apps.get_model(model_label)
            for model_field in _iter_crf_fields(model_cls):
                mdv.append(build_item_def(model_label, model_field))

        for model_label in models:
            model_cls = django_apps.get_model(model_label)
            for model_field in _iter_crf_fields(model_cls):
                cl = build_code_list(model_label, model_field)
                if cl is not None:
                    mdv.append(cl)
