from __future__ import annotations

from typing import TYPE_CHECKING

from django.apps import apps as django_apps
from django.contrib.admin.sites import all_sites
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from lxml import etree

from .constants import (
    DJANGO_TO_ODM_DATATYPE,
    EXCLUDED_FIELD_NAMES,
    EXCLUDED_FIELDSET_NAMES,
    ODM_NAMESPACE,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from edc_visit_schedule.visit import Visit
    from edc_visit_schedule.visit.crf import Crf
    from edc_visit_schedule.visit_schedule import VisitSchedule

    FieldsetTuple = tuple[str | None, dict]

NSMAP = {None: ODM_NAMESPACE}


def _oid(prefix: str, name: str) -> str:
    return f"{prefix}.{name}"


def _get_odm_datatype(field: models.Field) -> str:
    for field_cls in type(field).__mro__:
        if field_cls in DJANGO_TO_ODM_DATATYPE:
            return DJANGO_TO_ODM_DATATYPE[field_cls]
    return "text"


def _get_field_length(field: models.Field) -> int | None:
    if hasattr(field, "max_length") and field.max_length:
        return field.max_length
    return None


def _get_model_admin(
    model_cls: type[models.Model],
) -> object | None:
    for site in all_sites:
        if model_cls in site._registry:
            return site._registry[model_cls]
    return None


def _get_clinical_fieldsets(
    model_cls: type[models.Model],
) -> list[FieldsetTuple]:
    model_admin = _get_model_admin(model_cls)
    if model_admin is None or not hasattr(model_admin, "fieldsets"):
        return []
    fieldsets = model_admin.fieldsets or []
    result = []
    for name, options in fieldsets:
        if name and str(name) in EXCLUDED_FIELDSET_NAMES:
            continue
        fields = [f for f in options.get("fields", ()) if f not in EXCLUDED_FIELD_NAMES]
        if fields:
            result.append((name, {"fields": fields}))
    return result


def _get_field_by_name(model_cls: type[models.Model], field_name: str) -> models.Field | None:
    try:
        return model_cls._meta.get_field(field_name)
    except FieldDoesNotExist:
        return None


def _iter_fieldset_fields(
    model_cls: type[models.Model],
    fieldsets: list[FieldsetTuple],
) -> Iterator[models.Field]:
    seen: set[str] = set()
    for _name, options in fieldsets:
        for field_name in options.get("fields", ()):
            if field_name in seen:
                continue
            seen.add(field_name)
            field = _get_field_by_name(model_cls, field_name)
            if field is None:
                continue
            if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                continue
            yield field


def _iter_crf_fields(
    model_cls: type[models.Model],
) -> Iterator[models.Field]:
    fieldsets = _get_clinical_fieldsets(model_cls)
    if fieldsets:
        yield from _iter_fieldset_fields(model_cls, fieldsets)
    else:
        yield from _iter_model_meta_fields(model_cls)


def _iter_model_meta_fields(
    model_cls: type[models.Model],
) -> Iterator[models.Field]:
    for field in model_cls._meta.get_fields():
        if not isinstance(field, models.Field):
            continue
        if field.name in EXCLUDED_FIELD_NAMES:
            continue
        if isinstance(
            field,
            (
                models.ForeignKey,
                models.OneToOneField,
                models.ManyToManyField,
            ),
        ):
            continue
        yield field


def build_global_variables(
    protocol_name: str,
    protocol_title: str,
    study_description: str = "",
) -> etree._Element:
    gv = etree.Element("GlobalVariables")
    etree.SubElement(gv, "StudyName").text = protocol_name
    etree.SubElement(gv, "StudyDescription").text = study_description or protocol_title
    etree.SubElement(gv, "ProtocolName").text = protocol_name
    return gv


def build_protocol(
    visit_schedule: VisitSchedule,
) -> etree._Element:
    protocol = etree.Element("Protocol")
    order = 0
    for schedule in visit_schedule.schedules.values():
        for visit in schedule.visits.values():
            order += 1
            etree.SubElement(
                protocol,
                "StudyEventRef",
                StudyEventOID=_oid("SE", visit.code),
                OrderNumber=str(int(visit.timepoint)),
                Mandatory="Yes",
            )
    for name in collect_unique_unscheduled_collections(visit_schedule):
        order += 1
        etree.SubElement(
            protocol,
            "StudyEventRef",
            StudyEventOID=_oid("SE", f"UNSCHED.{name}"),
            OrderNumber=str(order),
            Mandatory="No",
        )
    for model_label in collect_common_models(visit_schedule):
        order += 1
        etree.SubElement(
            protocol,
            "StudyEventRef",
            StudyEventOID=_oid("SE", f"COMMON.{model_label}"),
            OrderNumber=str(order),
            Mandatory="No",
        )
    return protocol


def build_study_event_def(visit: Visit) -> etree._Element:
    sed = etree.Element(
        "StudyEventDef",
        OID=_oid("SE", visit.code),
        Name=visit.title,
        Repeating="No",
        Type="Scheduled",
    )
    for crf in _iter_visit_crfs(visit):
        model_label = crf.model
        etree.SubElement(
            sed,
            "FormRef",
            FormOID=_oid("F", model_label),
            OrderNumber=str(crf.show_order),
            Mandatory="Yes" if crf.required else "No",
        )
    for crf in _iter_visit_crfs_prn(visit):
        model_label = crf.model
        etree.SubElement(
            sed,
            "FormRef",
            FormOID=_oid("F", model_label),
            OrderNumber=str(crf.show_order),
            Mandatory="No",
        )
    return sed


def build_unscheduled_event_def(
    collection_name: str,
    crfs: tuple[Crf, ...],
) -> etree._Element:
    sed = etree.Element(
        "StudyEventDef",
        OID=_oid("SE", f"UNSCHED.{collection_name}"),
        Name=f"Unscheduled ({collection_name})",
        Repeating="Yes",
        Type="Unscheduled",
    )
    seen: set[str] = set()
    for crf in crfs:
        if crf.model not in seen:
            seen.add(crf.model)
            etree.SubElement(
                sed,
                "FormRef",
                FormOID=_oid("F", crf.model),
                OrderNumber=str(crf.show_order),
                Mandatory="Yes" if crf.required else "No",
            )
    return sed


def build_common_event_def(
    model_label: str,
    name: str,
) -> etree._Element:
    sed = etree.Element(
        "StudyEventDef",
        OID=_oid("SE", f"COMMON.{model_label}"),
        Name=name,
        Repeating="No",
        Type="Common",
    )
    etree.SubElement(
        sed,
        "FormRef",
        FormOID=_oid("F", model_label),
        OrderNumber="1",
        Mandatory="Yes",
    )
    return sed


def _iter_visit_crfs(visit: Visit) -> Iterator[Crf]:
    seen = set()
    for crf in visit.crfs:
        if crf.model not in seen:
            seen.add(crf.model)
            yield crf


def _iter_visit_crfs_prn(visit: Visit) -> Iterator[Crf]:
    scheduled_models = {crf.model for crf in visit.crfs}
    seen = set()
    for crf in visit.crfs_prn or ():
        if crf.model not in seen and crf.model not in scheduled_models:
            seen.add(crf.model)
            yield crf


def build_form_def(model_label: str) -> etree._Element:
    model_cls = django_apps.get_model(model_label)
    fieldsets = _get_clinical_fieldsets(model_cls)
    fd = etree.Element(
        "FormDef",
        OID=_oid("F", model_label),
        Name=_model_verbose_name(model_label),
        Repeating="No",
    )
    if fieldsets:
        for order, (name, _options) in enumerate(fieldsets, start=1):
            section_key = _fieldset_key(model_label, name, order)
            etree.SubElement(
                fd,
                "ItemGroupRef",
                ItemGroupOID=_oid("IG", section_key),
                OrderNumber=str(order),
                Mandatory="Yes",
            )
    else:
        etree.SubElement(
            fd,
            "ItemGroupRef",
            ItemGroupOID=_oid("IG", model_label),
            OrderNumber="1",
            Mandatory="Yes",
        )
    return fd


def build_item_group_defs(
    model_label: str,
) -> list[etree._Element]:
    model_cls = django_apps.get_model(model_label)
    fieldsets = _get_clinical_fieldsets(model_cls)
    if fieldsets:
        return _build_item_group_defs_from_fieldsets(model_label, model_cls, fieldsets)
    return [_build_item_group_def_from_meta(model_label, model_cls)]


def _build_item_group_defs_from_fieldsets(
    model_label: str,
    model_cls: type[models.Model],
    fieldsets: list[FieldsetTuple],
) -> list[etree._Element]:
    result = []
    for order, (name, options) in enumerate(fieldsets, start=1):
        section_key = _fieldset_key(model_label, name, order)
        section_name = str(name) if name else _model_verbose_name(model_label)
        igd = etree.Element(
            "ItemGroupDef",
            OID=_oid("IG", section_key),
            Name=section_name,
            Repeating="No",
        )
        field_order = 0
        for field_name in options.get("fields", ()):
            field = _get_field_by_name(model_cls, field_name)
            if field is None:
                continue
            if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                continue
            field_order += 1
            etree.SubElement(
                igd,
                "ItemRef",
                ItemOID=_oid("I", f"{model_label}.{field.name}"),
                OrderNumber=str(field_order),
                Mandatory="Yes" if not field.blank else "No",
            )
        if len(igd):
            result.append(igd)
    return result


def _build_item_group_def_from_meta(
    model_label: str,
    model_cls: type[models.Model],
) -> etree._Element:
    igd = etree.Element(
        "ItemGroupDef",
        OID=_oid("IG", model_label),
        Name=_model_verbose_name(model_label),
        Repeating="No",
    )
    for order, field in enumerate(_iter_model_meta_fields(model_cls), start=1):
        etree.SubElement(
            igd,
            "ItemRef",
            ItemOID=_oid("I", f"{model_label}.{field.name}"),
            OrderNumber=str(order),
            Mandatory="Yes" if not field.blank else "No",
        )
    return igd


def _fieldset_key(model_label: str, name: str | None, order: int) -> str:
    if name:
        slug = str(name).lower().replace(" ", "_")
        return f"{model_label}.{slug}.{order}"
    return f"{model_label}.section_{order}"


def build_item_def(model_label: str, field: models.Field) -> etree._Element:
    attrs: dict[str, str] = {
        "OID": _oid("I", f"{model_label}.{field.name}"),
        "Name": field.name,
        "DataType": _get_odm_datatype(field),
    }
    length = _get_field_length(field)
    if length:
        attrs["Length"] = str(length)
    item = etree.Element("ItemDef", **attrs)
    if field.verbose_name and field.verbose_name != field.name:
        desc = etree.SubElement(item, "Description")
        tt = etree.SubElement(desc, "TranslatedText")
        tt.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        tt.text = str(field.verbose_name)
    if hasattr(field, "choices") and field.choices:
        codelist_oid = _oid("CL", f"{model_label}.{field.name}")
        etree.SubElement(item, "CodeListRef", CodeListOID=codelist_oid)
    return item


def build_code_list(model_label: str, field: models.Field) -> etree._Element | None:
    if not hasattr(field, "choices") or not field.choices:
        return None
    cl = etree.Element(
        "CodeList",
        OID=_oid("CL", f"{model_label}.{field.name}"),
        Name=f"{field.name} choices",
        DataType="text",
    )
    for value, display in field.choices:
        if isinstance(display, (list, tuple)):
            for sub_value, sub_display in display:
                item = etree.SubElement(cl, "CodeListItem", CodedValue=str(sub_value))
                decode = etree.SubElement(item, "Decode")
                tt = etree.SubElement(decode, "TranslatedText")
                tt.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                tt.text = str(sub_display)
        else:
            item = etree.SubElement(cl, "CodeListItem", CodedValue=str(value))
            decode = etree.SubElement(item, "Decode")
            tt = etree.SubElement(decode, "TranslatedText")
            tt.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
            tt.text = str(display)
    return cl


def _model_verbose_name(model_label: str) -> str:
    model_cls = django_apps.get_model(model_label)
    return str(model_cls._meta.verbose_name)


def collect_unique_models(
    visit_schedule: VisitSchedule,
) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def _add(model_label: str) -> None:
        if model_label not in seen:
            seen.add(model_label)
            ordered.append(model_label)

    for schedule in visit_schedule.schedules.values():
        for visit in schedule.visits.values():
            for crf in visit.crfs:
                _add(crf.model)
            for crf in visit.crfs_prn or ():
                _add(crf.model)
            for crf in visit.crfs_unscheduled or ():
                _add(crf.model)

    for model_label in collect_common_models(visit_schedule):
        _add(model_label)

    return ordered


def collect_unique_unscheduled_collections(
    visit_schedule: VisitSchedule,
) -> dict[str, tuple[Crf, ...]]:
    collections: dict[str, tuple[Crf, ...]] = {}
    for schedule in visit_schedule.schedules.values():
        for visit in schedule.visits.values():
            if visit.crfs_unscheduled:
                name = (
                    getattr(visit.crfs_unscheduled, "name", None)
                    or f"unscheduled_{visit.code}"
                )
                if name not in collections:
                    collections[name] = tuple(visit.crfs_unscheduled)
    return collections


def collect_common_models(
    visit_schedule: VisitSchedule,
) -> list[str]:
    return [
        model_label
        for model_label in [
            visit_schedule.death_report_model,
            visit_schedule.offstudy_model,
        ]
        if model_label and _model_exists(model_label)
    ]


def _model_exists(model_label: str) -> bool:
    try:
        django_apps.get_model(model_label)
    except LookupError:
        return False
    return True
