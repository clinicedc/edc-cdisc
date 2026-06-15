from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from edc_protocol.research_protocol_config import ResearchProtocolConfig
from lxml import etree
from tqdm import tqdm

from .clinical_data_builders import (
    _keyed_metadata_qs,
    build_clinical_data,
    build_form_data,
    build_study_event_data,
    build_subject_data,
    get_changed_crf_instances,
    get_subject_visits,
    get_submitted_crf_instances,
)
from .constants import ODM_NAMESPACE, ODM_VERSION
from .serializer import ODMStudySerializer

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db import models
    from edc_visit_schedule.visit_schedule import VisitSchedule

NSMAP = {None: ODM_NAMESPACE}


def _group_visits_by_subject(
    visits_qs: models.QuerySet,
) -> dict[str, list]:
    grouped: dict[str, list] = defaultdict(list)
    for visit in visits_qs:
        grouped[visit.subject_identifier].append(visit)
    return dict(grouped)


@dataclass
class ODMClinicalDataSerializer:
    visit_schedule: VisitSchedule
    subject_identifiers: Iterable[str] | None = None
    study_oid: str = ""
    metadata_version_oid: str = "MDV.1"
    include_nulls: bool = False

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
        grouped = _group_visits_by_subject(visits_qs)

        subject_data_elements: list[etree._Element] = []
        for subject_id, visits in tqdm(grouped.items(), desc="Snapshot", unit="subject"):
            subject_data_elements.append(self._build_subject_data(subject_id, visits))

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
                build_form_data(model_label, instance, include_nulls=self.include_nulls)
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


@dataclass
class ODMTransactionalSerializer:
    """Export CRF data changed since a cutoff as ODM Transactional XML.

    Each FormData element carries a TransactionType of "Insert" or
    "Update" depending on whether the CRF was created or modified
    after ``since``.
    """

    visit_schedule: VisitSchedule
    since: datetime
    subject_identifiers: Iterable[str] | None = None
    study_oid: str = ""
    metadata_version_oid: str = "MDV.1"
    include_nulls: bool = False

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
            FileType="Transactional",
            CreationDateTime=now,
            ODMVersion=ODM_VERSION,
            Originator="clinicedc/edc-cdisc",
        )

    def _build_clinical_data(self) -> etree._Element:
        visits_qs = get_subject_visits(
            visit_schedule_name=self.visit_schedule.name,
            subject_identifiers=self.subject_identifiers,
        )
        grouped = _group_visits_by_subject(visits_qs)

        subject_data_elements: list[etree._Element] = []
        for subject_id, visits in tqdm(grouped.items(), desc="Transactional", unit="subject"):
            sd = self._build_subject_data(subject_id, visits)
            if sd is not None:
                subject_data_elements.append(sd)

        return build_clinical_data(
            study_oid=self.study_oid,
            metadata_version_oid=self.metadata_version_oid,
            subject_data_elements=subject_data_elements,
        )

    def _build_subject_data(
        self,
        subject_identifier: str,
        visits: list,
    ) -> etree._Element | None:
        study_event_elements: list[etree._Element] = []
        for visit in visits:
            metadata_qs = _keyed_metadata_qs(
                subject_identifier,
                visit.visit_code,
                visit.visit_code_sequence,
                visit.visit_schedule_name,
                visit.schedule_name,
            )
            changed = get_changed_crf_instances(metadata_qs, since=self.since)
            form_data_elements = [
                build_form_data(
                    model_label,
                    instance,
                    transaction_type=txn_type,
                    include_nulls=self.include_nulls,
                )
                for model_label, instance, txn_type in changed
            ]
            if form_data_elements:
                study_event_elements.append(
                    build_study_event_data(
                        visit_code=visit.visit_code,
                        visit_code_sequence=visit.visit_code_sequence,
                        form_data_elements=form_data_elements,
                    )
                )
        if not study_event_elements:
            return None
        return build_subject_data(
            subject_identifier=subject_identifier,
            study_event_elements=study_event_elements,
        )


@dataclass
class ODMSnapshotSerializer:
    """Combined Snapshot: Study metadata + ClinicalData in one ODM file."""

    visit_schedule: VisitSchedule
    subject_identifiers: Iterable[str] | None = None
    study_oid: str = ""
    study_name: str = ""
    study_description: str = ""
    metadata_version_oid: str = "MDV.1"
    metadata_version_name: str = "Version 1"
    include_nulls: bool = False

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
        return etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    def to_etree(self) -> etree._Element:
        return self._build_root()

    def _build_root(self) -> etree._Element:
        now = datetime.now(tz=UTC).isoformat()
        root = etree.Element(
            "ODM",
            nsmap=NSMAP,
            FileOID=f"{self.study_oid}.ODM.{now}",
            FileType="Snapshot",
            CreationDateTime=now,
            ODMVersion=ODM_VERSION,
            Originator="clinicedc/edc-cdisc",
        )

        study_serializer = ODMStudySerializer(
            visit_schedule=self.visit_schedule,
            study_oid=self.study_oid,
            study_name=self.study_name,
            study_description=self.study_description,
            metadata_version_oid=self.metadata_version_oid,
            metadata_version_name=self.metadata_version_name,
        )
        root.append(study_serializer._build_study())

        clinical_serializer = ODMClinicalDataSerializer(
            visit_schedule=self.visit_schedule,
            subject_identifiers=self.subject_identifiers,
            study_oid=self.study_oid,
            metadata_version_oid=self.metadata_version_oid,
            include_nulls=self.include_nulls,
        )
        root.append(clinical_serializer._build_clinical_data())

        return root
