from __future__ import annotations

import itertools
import operator
from functools import cached_property

from django.apps import apps as django_apps
from lxml import etree

from ..constants import HISTORY_TYPE_MAP, LOCATION, USER
from ..utils import oid
from .admin_data_mixin import AdminDataMixin
from .clinical_data_serializer import ClinicalDataSerializer
from .metadata_serializer import MetadataSerializer
from .visit_schedule_serializer import RelatedVisitProtocol, VisitScheduleSerializer


class TransactionalClinicalDataSerializer(ClinicalDataSerializer):
    """``ClinicalData`` where each ``FormData`` is one simple_history row,
    carrying a ``TransactionType`` (Insert/Update/Remove) and an ``AuditRecord``.

    Reuses the snapshot subject/visit scaffolding (``build`` /
    ``build_subject_data``) but overrides the leaf builders to iterate
    ``model_cls.history`` instead of current rows.  Users and sites seen in the
    audit records are accumulated for the ``AdminData`` catalog.
    """

    file_type = "Transactional"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.referenced_users: set[str] = set()
        self.referenced_sites: set[int] = set()

    def build_study_event_data(
        self, subject_visit: RelatedVisitProtocol
    ) -> etree._Element | None:
        form_elements: list[etree._Element] = []
        for crf in subject_visit.visit.all_crfs:
            rows = crf.model_cls.history.filter(subject_visit_id=subject_visit.id).order_by(
                "history_date"
            )
            form_elements += [self.build_history_form_data(crf.model, row) for row in rows]
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

    def build_common_event_data(self, subject_identifier: str) -> list[etree._Element]:
        models = [*self.get_common_models()]
        if screening_model := self.get_screening_model():
            models.append(screening_model)
        elements: list[etree._Element] = []
        for model in models:
            model_cls = django_apps.get_model(model)
            rows = model_cls.history.filter(subject_identifier=subject_identifier).order_by(
                "history_date"
            )
            form_elements = [self.build_history_form_data(model, row) for row in rows]
            if not form_elements:
                continue
            element = etree.Element(
                "StudyEventData", StudyEventOID=self.common_event_oid(model)
            )
            for form_element in form_elements:
                element.append(form_element)
            elements.append(element)
        return elements

    def build_consent_event_data(self, subject_identifier: str) -> list[etree._Element]:
        consent_model = self.get_consent_model()
        if not consent_model:
            return []
        model_cls = django_apps.get_model(consent_model)
        rows = model_cls.history.filter(subject_identifier=subject_identifier).order_by(
            "version", "history_date"
        )
        elements: list[etree._Element] = []
        for version, group in itertools.groupby(rows, key=operator.attrgetter("version")):
            element = etree.Element(
                "StudyEventData",
                StudyEventOID=self.common_event_oid(consent_model),
                StudyEventRepeatKey=str(version),
            )
            for row in group:
                element.append(self.build_history_form_data(consent_model, row))
            elements.append(element)
        return elements

    def build_history_form_data(self, model: str, history_row) -> etree._Element:
        return self.build_form_data(
            model,
            history_row,
            transaction_type=HISTORY_TYPE_MAP.get(history_row.history_type),
            audit_record=self.build_audit_record(history_row),
        )

    def build_audit_record(self, history_row) -> etree._Element:
        element = etree.Element("AuditRecord")
        # children in XSD order: UserRef, LocationRef, DateTimeStamp, ReasonForChange
        if username := self._history_username(history_row):
            etree.SubElement(element, "UserRef", UserOID=oid(USER, username))
            self.referenced_users.add(username)
        if site_id := getattr(history_row, "site_id", None):
            etree.SubElement(element, "LocationRef", LocationOID=oid(LOCATION, str(site_id)))
            self.referenced_sites.add(site_id)
        etree.SubElement(element, "DateTimeStamp").text = history_row.history_date.isoformat()
        if reason := getattr(history_row, "history_change_reason", None):
            etree.SubElement(element, "ReasonForChange").text = reason
        return element

    @staticmethod
    def _history_username(history_row) -> str:
        if history_row.history_user_id:
            user = history_row.history_user  # getter resolves the auth user
            if user is not None:
                return user.username
        # fall back to the un-editable audit username on the row
        return getattr(history_row, "user_modified", "") or getattr(
            history_row, "user_created", ""
        )


class TransactionalSerializer(AdminDataMixin, VisitScheduleSerializer):
    """ODM root for the audit trail: ``Study`` + ``AdminData`` + transactional
    ``ClinicalData``.  ClinicalData is built first so ``AdminData`` knows which
    users/sites to define.
    """

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("file_type", "Transactional")
        super().__init__(*args, **kwargs)

    def to_etree(self) -> etree._Element:
        root = super().to_etree()  # fresh <ODM FileType="Transactional">
        clinical = self.clinical_data_serializer
        clinical_element = clinical.build()  # records referenced users/sites
        admin_element = self.build_admin_data(
            clinical.referenced_users,
            clinical.referenced_sites,
            clinical.metadata_version_oid,
        )
        root.append(self.metadata_serializer.build())  # <Study>
        root.append(admin_element)  # <AdminData>
        root.append(clinical_element)  # <ClinicalData>
        return root

    @cached_property
    def metadata_serializer(self) -> MetadataSerializer:
        return self._make(MetadataSerializer)

    @cached_property
    def clinical_data_serializer(self) -> TransactionalClinicalDataSerializer:
        return self._make(TransactionalClinicalDataSerializer)

    def _make(self, cls):
        return cls(
            edc_module_name=self.edc_module_name,
            protocol_oid=self.protocol_oid,
            visit_schedule=self.visit_schedule,
            subject_identifiers=self.subject_identifiers,
            include_nulls=self.include_nulls,
        )
