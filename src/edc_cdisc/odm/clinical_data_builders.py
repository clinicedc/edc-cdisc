from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from django.apps import apps as django_apps
from django.db import models
from lxml import etree

from .builders import (
    _fieldset_key,
    _get_clinical_fieldsets,
    _get_field_by_name,
    _iter_crf_fields,
    _oid,
)
from .constants import ODM_NAMESPACE

if TYPE_CHECKING:
    from collections.abc import Iterable

NSMAP = {None: ODM_NAMESPACE}

_SERIALIZE_MAP: list[tuple[type, callable]] = [
    (bool, lambda v: "true" if v else "false"),
    (datetime, lambda v: v.isoformat()),
    (date, lambda v: v.isoformat()),
    (time, lambda v: v.isoformat()),
    (Decimal, str),
    (float, str),
    (int, str),
    (UUID, str),
]


def serialize_value(value: object) -> str | None:
    if value is None:
        return None
    for cls, fn in _SERIALIZE_MAP:
        if isinstance(value, cls):
            return fn(value)
    return str(value)


def build_clinical_data(
    study_oid: str,
    metadata_version_oid: str,
    subject_data_elements: list[etree._Element],
) -> etree._Element:
    cd = etree.Element(
        "ClinicalData",
        StudyOID=study_oid,
        MetaDataVersionOID=metadata_version_oid,
    )
    for sd in subject_data_elements:
        cd.append(sd)
    return cd


def build_subject_data(
    subject_identifier: str,
    study_event_elements: list[etree._Element],
    transaction_type: str | None = None,
) -> etree._Element:
    attrs: dict[str, str] = {"SubjectKey": subject_identifier}
    if transaction_type:
        attrs["TransactionType"] = transaction_type
    sd = etree.Element("SubjectData", **attrs)
    for se in study_event_elements:
        sd.append(se)
    return sd


def build_study_event_data(
    visit_code: str,
    visit_code_sequence: int,
    form_data_elements: list[etree._Element],
    transaction_type: str | None = None,
) -> etree._Element:
    attrs: dict[str, str] = {
        "StudyEventOID": _oid("SE", visit_code),
    }
    if visit_code_sequence > 0:
        attrs["StudyEventRepeatKey"] = str(visit_code_sequence)
    if transaction_type:
        attrs["TransactionType"] = transaction_type
    sed = etree.Element("StudyEventData", **attrs)
    for fd in form_data_elements:
        sed.append(fd)
    return sed


def build_form_data(
    model_label: str,
    instance: models.Model,
    transaction_type: str | None = None,
) -> etree._Element:
    model_cls = type(instance)
    attrs: dict[str, str] = {"FormOID": _oid("F", model_label)}
    if transaction_type:
        attrs["TransactionType"] = transaction_type
    fd = etree.Element("FormData", **attrs)
    fieldsets = _get_clinical_fieldsets(model_cls)
    if fieldsets:
        _append_item_groups_from_fieldsets(fd, model_label, model_cls, instance, fieldsets)
    else:
        _append_item_group_from_meta(fd, model_label, model_cls, instance)
    return fd


def _append_item_groups_from_fieldsets(
    fd: etree._Element,
    model_label: str,
    model_cls: type[models.Model],
    instance: models.Model,
    fieldsets: list[tuple],
) -> None:
    for order, (name, options) in enumerate(fieldsets, start=1):
        section_key = _fieldset_key(model_label, name, order)
        igd = etree.Element(
            "ItemGroupData",
            ItemGroupOID=_oid("IG", section_key),
        )
        for field_name in options.get("fields", ()):
            field = _get_field_by_name(model_cls, field_name)
            if field is None:
                continue
            if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                continue
            value = getattr(instance, field.attname, None)
            serialized = serialize_value(value)
            if serialized is not None:
                etree.SubElement(
                    igd,
                    "ItemData",
                    ItemOID=_oid("I", f"{model_label}.{field.name}"),
                    Value=serialized,
                )
        if len(igd):
            fd.append(igd)


def _append_item_group_from_meta(
    fd: etree._Element,
    model_label: str,
    model_cls: type[models.Model],
    instance: models.Model,
) -> None:
    igd = etree.Element(
        "ItemGroupData",
        ItemGroupOID=_oid("IG", model_label),
    )
    for model_field in _iter_crf_fields(model_cls):
        value = getattr(instance, model_field.attname, None)
        serialized = serialize_value(value)
        if serialized is not None:
            etree.SubElement(
                igd,
                "ItemData",
                ItemOID=_oid("I", f"{model_label}.{model_field.name}"),
                Value=serialized,
            )
    if len(igd):
        fd.append(igd)


def _keyed_metadata_qs(
    subject_identifier: str,
    visit_code: str,
    visit_code_sequence: int,
    visit_schedule_name: str,
    schedule_name: str,
) -> models.QuerySet:
    crf_metadata_cls = django_apps.get_model("edc_metadata.crfmetadata")
    return crf_metadata_cls.objects.filter(
        subject_identifier=subject_identifier,
        visit_code=visit_code,
        visit_code_sequence=visit_code_sequence,
        visit_schedule_name=visit_schedule_name,
        schedule_name=schedule_name,
        entry_status="KEYED",
    ).order_by("show_order")


def get_submitted_crf_instances(
    subject_identifier: str,
    visit_code: str,
    visit_code_sequence: int,
    visit_schedule_name: str,
    schedule_name: str,
) -> list[tuple[str, models.Model]]:
    results: list[tuple[str, models.Model]] = []
    for metadata in _keyed_metadata_qs(
        subject_identifier,
        visit_code,
        visit_code_sequence,
        visit_schedule_name,
        schedule_name,
    ):
        instance = metadata.model_instance
        if instance is not None:
            results.append((metadata.model, instance))
    return results


def get_changed_crf_instances(
    metadata_qs: models.QuerySet,
    since: datetime,
) -> list[tuple[str, models.Model, str]]:
    """Return (model_label, instance, transaction_type) for CRFs
    changed since the given timestamp.

    TransactionType is "Insert" if created >= since,
    "Update" if modified >= since but created < since.
    """
    results: list[tuple[str, models.Model, str]] = []
    for metadata in metadata_qs:
        instance = metadata.model_instance
        if instance is None:
            continue
        if instance.created >= since:
            results.append((metadata.model, instance, "Insert"))
        elif instance.modified >= since:
            results.append((metadata.model, instance, "Update"))
    return results


def get_subject_visits(
    visit_schedule_name: str,
    subject_identifiers: Iterable[str] | None = None,
) -> models.QuerySet:
    subject_visit_cls = django_apps.get_model("edc_visit_tracking.subjectvisit")
    qs = subject_visit_cls.objects.filter(
        visit_schedule_name=visit_schedule_name,
    ).order_by("subject_identifier", "visit_code", "visit_code_sequence")
    if subject_identifiers is not None:
        qs = qs.filter(subject_identifier__in=list(subject_identifiers))
    return qs
