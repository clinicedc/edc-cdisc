from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import groupby
from operator import attrgetter
from typing import TYPE_CHECKING

from edc_protocol.research_protocol_config import ResearchProtocolConfig
from lxml import etree

from .clinical_data_builders import (
    build_clinical_data,
    build_form_data,
    build_study_event_data,
    build_subject_data,
    get_subject_visits,
    get_submitted_crf_instances,
)
from .constants import ODM_NAMESPACE, ODM_VERSION

if TYPE_CHECKING:
    from collections.abc import Iterable

    from edc_visit_schedule.visit_schedule import VisitSchedule

NSMAP = {None: ODM_NAMESPACE}


@dataclass
class ODMClinicalDataSerializer:
    visit_schedule: VisitSchedule
    subject_identifiers: Iterable[str] | None = None
    study_oid: str = ""
    metadata_version_oid: str = "MDV.1"

    _protocol_config: ResearchProtocolConfig = field(
        init=False, repr=False, default_factory=ResearchProtocolConfig
    )

    def __post_init__(self) -> None:
        if not self.study_oid:
            self.study_oid = f"S.{self._protocol_config.protocol}"

    def to_xml(self) -> bytes:
        root = self._build_root()
        clinical_data = self._build_clinical_data()
        root.append(clinical_data)
        return etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    def to_etree(self) -> etree._Element:
        root = self._build_root()
        clinical_data = self._build_clinical_data()
        root.append(clinical_data)
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

    def _build_clinical_data(self) -> etree._Element:
        visits_qs = get_subject_visits(
            visit_schedule_name=self.visit_schedule.name,
            subject_identifiers=self.subject_identifiers,
        )

        subject_data_elements: list[etree._Element] = []
        for subject_id, visits in groupby(visits_qs, key=attrgetter("subject_identifier")):
            subject_data_elements.append(self._build_subject_data(subject_id, list(visits)))

        return build_clinical_data(
            study_oid=self.study_oid,
            metadata_version_oid=self.metadata_version_oid,
            subject_data_elements=subject_data_elements,
        )

    def _build_subject_data(
        self,
        subject_identifier: str,
        visits: list,
    ) -> etree._Element:
        study_event_elements: list[etree._Element] = []
        for visit in visits:
            crf_instances = get_submitted_crf_instances(
                subject_identifier=subject_identifier,
                visit_code=visit.visit_code,
                visit_code_sequence=visit.visit_code_sequence,
                visit_schedule_name=visit.visit_schedule_name,
                schedule_name=visit.schedule_name,
            )
            form_data_elements = [
                build_form_data(model_label, instance)
                for model_label, instance in crf_instances
            ]
            if form_data_elements:
                study_event_elements.append(
                    build_study_event_data(
                        visit_code=visit.visit_code,
                        visit_code_sequence=visit.visit_code_sequence,
                        form_data_elements=form_data_elements,
                    )
                )
        return build_subject_data(
            subject_identifier=subject_identifier,
            study_event_elements=study_event_elements,
        )
