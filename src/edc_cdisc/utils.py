from __future__ import annotations

import hashlib
import warnings
from datetime import date, datetime, time
from typing import TYPE_CHECKING

from django.contrib import admin
from django.contrib.admin.sites import all_sites
from django.db import models
from django.http import HttpRequest
from lxml import etree

from .constants import (
    DJANGO_TO_ODM_DATATYPE,
    EXCLUDED_FIELD_NAMES,
    EXCLUDED_FIELDSET_NAMES,
    ODM_SCHEMA_PATH,
)
from .exceptions import ModelAdminNotFoundError

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from edc_visit_schedule.visit_schedule import VisitSchedule

    FieldsetTuple = tuple[str | None, dict[str, tuple[str, ...]]]


def oid(prefix: str, name: str) -> str:
    return f"{prefix}.{name}"


def get_odm_datatype(field: models.Field) -> str:
    for field_cls in type(field).__mro__:
        if field_cls in DJANGO_TO_ODM_DATATYPE:
            return DJANGO_TO_ODM_DATATYPE[field_cls]
    return "text"


def serialize_value(value: object) -> str | None:
    """Convert a Python value to an ODM ItemData string, or None if null.

    None is the only "null" — an empty string is real (entered-but-blank)
    data and serializes to "".
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)


def get_related_visits(
    visit_schedule: VisitSchedule,
    subject_identifiers: Iterable[str] | None = None,
) -> models.QuerySet:
    """Returns a related_visit_model queryset"""
    opts = dict(visit_schedule_name=visit_schedule.name)
    if subject_identifiers:
        opts.update({"subject_identifier__in": subject_identifiers})
    return visit_schedule.visit_model_cls.objects.filter(**opts).order_by(
        "subject_identifier", "visit_code", "visit_code_sequence"
    )


def get_field_length(field: models.Field) -> int | None:
    if hasattr(field, "max_length") and field.max_length:
        return field.max_length
    return None


def get_model_admin_or_raise(
    model_cls: type[models.Model],
) -> admin.ModelAdmin:
    model_admin = None
    for site in all_sites:
        if model_cls in site._registry:
            model_admin = site._registry[model_cls]
            if (
                not hasattr(model_admin, "fieldsets")
                or getattr(model_admin, "fieldsets", None) is None
            ):
                warnings.warn(
                    "ModelAdmin missing fieldsets. Using get_fieldsets(). "
                    f"Got {model_cls._meta.label_lower}.",
                    UserWarning,
                    stacklevel=2,
                )
    if not model_admin:
        raise ModelAdminNotFoundError(model_cls)
    return model_admin


def get_modeladmin_fieldsets(
    model_cls: type[models.Model],
) -> list[FieldsetTuple]:
    result = []
    model_admin = get_model_admin_or_raise(model_cls)
    fieldsets = getattr(model_admin, "fieldsets", None)
    if not fieldsets:
        fieldsets = model_admin.get_fieldsets(HttpRequest())
    for section_name, opts in fieldsets:
        if section_name and str(section_name) in EXCLUDED_FIELDSET_NAMES:
            continue
        fields = [f for f in opts.get("fields") if f not in EXCLUDED_FIELD_NAMES]
        if fields:
            result.append((section_name, {"fields": fields}))
    return result


def fieldset_key(model_label: str, name: str | None, order: int) -> str:
    if name:
        slug = str(name).lower().replace(" ", "_")
        return f"{model_label}.{slug}.{order}"
    return f"{model_label}.section_{order}"


def is_encrypted_field(field: models.Field) -> bool:
    """True if ``field`` is a django_crypto_fields encrypted field (PII).

    Encrypted fields are never exported (metadata or data) anywhere in
    edc-cdisc.
    """
    from django_crypto_fields.fields.base_field import BaseField  # noqa: PLC0415

    return isinstance(field, BaseField)


def iter_crf_sections(
    model_cls: type[models.Model],
) -> Iterator[tuple[int, str | None, list[models.Field]]]:
    """Yield ``(section_order, section_name, fields)`` for each non-empty
    admin fieldset section, skipping encrypted (PII) fields.

    This is the single field-selection source shared by the metadata
    (``FormDef`` / ``ItemGroupDef`` / ``ItemDef``) and data (``FormData``)
    builders, so they cannot drift.  ``section_order`` is the fieldset's
    positional index and is kept stable (it is not renumbered when a section
    drops out) so ``ItemGroupOID``\\s do not shift.

    Note: relation fields (FK / O2O / M2M) are *included* for now (emitted as
    text); proper relation handling is a later step.
    """
    for index, (name, opts) in enumerate(get_modeladmin_fieldsets(model_cls), start=1):
        fields = []
        for field_name in opts.get("fields"):
            field = model_cls._meta.get_field(field_name)
            if is_encrypted_field(field):
                continue
            fields.append(field)
        if fields:
            yield index, name, fields


def iter_fieldset_fields(model_cls: type[models.Model]) -> Iterator[models.Field]:
    """Deduplicated flat view of :func:`iter_crf_sections` (for ``ItemDef`` /
    ``CodeList`` building)."""
    seen: set[str] = set()
    for _index, _name, fields in iter_crf_sections(model_cls):
        for field in fields:
            if field.name in seen:
                continue
            seen.add(field.name)
            yield field


def compute_fingerprint(mdv: etree._Element) -> str:
    clone = etree.fromstring(etree.tostring(mdv))  # cheap detached copy
    clone.attrib.pop("OID", None)
    clone.attrib.pop("Name", None)
    canonical = etree.tostring(clone, method="c14n")  # C14N: stable attr order/ns/whitespace
    return hashlib.sha256(canonical).hexdigest()[:12]


def validate_odm(doc) -> list[str]:
    if isinstance(doc, bytes):
        doc = etree.fromstring(doc)
    problems = []
    schema = etree.XMLSchema(etree.parse(str(ODM_SCHEMA_PATH)))
    if not schema.validate(doc):
        problems += [f"XSD line {e.line}: {e.message}" for e in schema.error_log]
    defined = {e.get("OID") for e in doc.iter() if e.get("OID")}
    ref_attrs = (
        "StudyOID",
        "MetaDataVersionOID",
        "StudyEventOID",
        "FormOID",
        "ItemGroupOID",
        "ItemOID",
        "CodeListOID",
    )
    refs = {e.get(a) for e in doc.iter() for a in ref_attrs if e.get(a)}
    problems += [f"dangling ref: {r}" for r in sorted(refs - defined)]
    return problems
