import itertools
import operator
import uuid
from collections.abc import Iterable
from datetime import datetime
from functools import cached_property
from typing import Protocol

from clinicedc_constants import YES
from django.apps import apps as django_apps
from django.core.exceptions import ObjectDoesNotExist
from lxml import etree

from ..constants import FORM, ITEM, ITEM_GROUP
from ..exceptions import NegativeVisitCodeSequenceError
from ..utils import (
    compute_fingerprint,
    fieldset_key,
    iter_crf_sections,
    oid,
    serialize_value,
)
from .metadata_serializer import MetadataSerializer
from .visit_schedule_serializer import RelatedVisitProtocol, VisitScheduleSerializer


class CrfProtocol(Protocol):
    subject_visit_id: uuid.UUID
    report_datetime: datetime
    created: datetime
    modified: datetime


def compute_metadata_version_oid(visit_schedule, edc_module_name) -> str:
    mdv = MetadataSerializer(
        visit_schedule=visit_schedule, edc_module_name=edc_module_name
    ).build_metadata_version()
    return f"MDV.{compute_fingerprint(mdv)}"


class ClinicalDataSerializer(VisitScheduleSerializer):
    file_type = "Snapshot"

    def to_etree(self) -> etree._Element:
        root = super().to_etree()  # <ODM> (fresh, FileType=self.file_type)
        root.append(self.build())
        return root

    def check_subject_visit(self) -> None:
        if self.related_visit_model_cls.objects.filter(visit_code_sequence__lt=0).exists():
            raise NegativeVisitCodeSequenceError()

    @cached_property
    def metadata_version_oid(self) -> str:
        return compute_metadata_version_oid(self.visit_schedule, self.edc_module_name)

    def build(self) -> etree._Element:
        self.check_subject_visit()
        element = etree.Element(
            "ClinicalData",
            StudyOID=self.protocol_oid,
            MetaDataVersionOID=self.metadata_version_oid,
        )
        # Drive the subject set off the enrolled master list (RegisteredSubject),
        # so an enrolled subject with no visits (but a common/screening event)
        # still appears.  Visits are prefetched once and grouped by subject.
        visits_by_subject = self._visits_by_subject()
        for subject_identifier in self._enrolled_subject_identifiers():
            subject_element = self.build_subject_data(
                subject_identifier, visits_by_subject.get(subject_identifier, [])
            )
            if subject_element is not None:
                element.append(subject_element)
        return element

    def _enrolled_subject_identifiers(self):
        qs = self.registered_subject_model_cls.objects.all()
        if self.subject_identifiers:
            qs = qs.filter(subject_identifier__in=self.subject_identifiers)
        return qs.values_list("subject_identifier", flat=True).order_by("subject_identifier")

    def _visits_by_subject(self) -> dict[str, list[RelatedVisitProtocol]]:
        opts = {}
        if self.subject_identifiers:
            opts.update(subject_identifier__in=self.subject_identifiers)
        qs = self.related_visit_model_cls.objects.filter(
            visit_schedule_name=self.visit_schedule.name, **opts
        ).order_by("subject_identifier", "report_datetime")
        return {
            subject_identifier: list(visits)
            for subject_identifier, visits in itertools.groupby(
                qs, key=operator.attrgetter("subject_identifier")
            )
        }

    def build_subject_data(
        self, subject_identifier: str, subject_visits: list[RelatedVisitProtocol]
    ) -> etree._Element | None:
        event_elements: list[etree._Element] = []

        for subject_visit in subject_visits:
            event_element = self.build_study_event_data(subject_visit)
            if event_element is not None:
                event_elements.append(event_element)
        event_elements += self.build_common_event_data(subject_identifier)

        if not event_elements:
            return None

        element = etree.Element("SubjectData", SubjectKey=subject_identifier)
        for event_element in event_elements:
            element.append(event_element)
        return element

    def build_study_event_data(
        self, subject_visit: RelatedVisitProtocol
    ) -> etree._Element | None:
        crfs = self.get_crfs_for_visit(subject_visit)
        form_elements = [
            self.build_form_data(model, instance, None) for model, instance in crfs
        ]
        if not form_elements:
            return None

        if subject_visit.visit_code_sequence == 0:
            attrs = {"StudyEventOID": self.scheduled_event_oid(subject_visit.visit_code)}
        else:
            attrs = {
                "StudyEventOID": self.unscheduled_event_oid(subject_visit.visit_code),
                "StudyEventRepeatKey": str(subject_visit.visit_code_sequence),
            }
        element = etree.Element("StudyEventData", **attrs)
        for form_element in form_elements:
            element.append(form_element)
        return element

    def build_form_data(
        self, model: str, instance, transaction_type: str | None = None
    ) -> etree._Element:
        model_cls = type(instance)
        attrs = {"FormOID": oid(FORM, model)}
        if transaction_type:
            attrs["TransactionType"] = transaction_type
        element = etree.Element("FormData", **attrs)

        # SAME field selection as the metadata side → ItemGroupOID/ItemOID
        # line up (encrypted fields skipped, sections kept stable).
        for index, name, fields in iter_crf_sections(model_cls):
            group = etree.Element(
                "ItemGroupData",
                ItemGroupOID=oid(ITEM_GROUP, fieldset_key(model, name, index)),
            )
            for field in fields:
                item_oid = oid(ITEM, f"{model}.{field.name}")
                # field.attname → FK reads the uuid pk (FK-as-text for now)
                value = serialize_value(getattr(instance, field.attname, None))
                if value is not None:
                    etree.SubElement(group, "ItemData", ItemOID=item_oid, Value=value)
                elif self.include_nulls:
                    etree.SubElement(group, "ItemData", ItemOID=item_oid, IsNull=YES)
            if len(group):  # skip empty groups (sparse data)
                element.append(group)
        return element

    def build_common_event_data(self, subject_identifier: str) -> list[etree._Element]:
        """Death report / offstudy — singleton (or zero) per subject."""
        elements: list[etree._Element] = []
        for model in self.get_common_models():
            instance = (
                django_apps.get_model(model)
                .objects.filter(subject_identifier=subject_identifier)
                .first()
            )
            if instance is None:
                continue
            element = etree.Element(
                "StudyEventData", StudyEventOID=self.common_event_oid(model)
            )
            element.append(self.build_form_data(model, instance))
            elements.append(element)
        return elements

    @staticmethod
    def get_crfs_for_visit(
        subject_visit: RelatedVisitProtocol,
    ) -> Iterable[tuple[str, CrfProtocol]]:
        for crf in subject_visit.visit.all_crfs:
            try:
                obj: CrfProtocol = crf.model_cls.objects.get(subject_visit=subject_visit)
            except ObjectDoesNotExist:
                continue
            yield crf.model, obj
