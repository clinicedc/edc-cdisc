from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from clinicedc_constants import NO, YES
from django.apps import apps as django_apps
from lxml import etree

from ..constants import (
    CODELIST,
    COMMON_TYPE,
    FORM,
    ITEM,
    ITEM_GROUP,
    SCHEDULED_TYPE,
    UNSCHEDULED_TYPE,
)
from ..exceptions import ProtocolSerializerError
from ..utils import (
    compute_fingerprint,
    fieldset_key,
    get_modeladmin_fieldsets,
    get_odm_datatype,
    iter_fieldset_fields,
    oid,
)
from .visit_schedule_serializer import VisitScheduleSerializer

if TYPE_CHECKING:
    from edc_visit_schedule.visit import Crf, Visit


class MetadataSerializer(VisitScheduleSerializer):
    """
      MetaDataVersion
    ├─ Protocol          ← the "table of contents": StudyEventRef list
    ├─ StudyEventDef …   ← the actual event definitions
    ├─ FormDef …
    ├─ ItemGroupDef …
    ├─ ItemDef …
    └─ CodeList …

    import hashlib
    from edc_cdisc.serializers import MetadataSerializer
    from edc_visit_schedule.site_visit_schedules import site_visit_schedules

    visit_schedule = site_visit_schedules.visit_schedules.get("visit_schedule")
    ps = MetadataSerializer(edc_module_name="meta_edc", visit_schedule=visit_schedule)
    ele = etree.tostring(ps.to_etree(), method="c14n")
    hashlib.sha256(ele).hexdigest()[:12]
    """

    def to_etree(self) -> etree._Element:
        element = super().to_etree()
        element.append(self.build())
        return element

    def build(self) -> etree._Element:
        study_element = etree.Element("Study", OID=self.protocol_oid)
        study_element.append(self.global_variables)
        mdv_element = self.build_metadata_version()
        fp = compute_fingerprint(mdv_element)
        mdv_element.set("OID", f"MDV.{fp}")
        mdv_element.set("Name", f"metadata {fp}")
        study_element.append(mdv_element)
        return study_element

    def build_metadata_version(self) -> etree._Element:
        element = etree.Element("MetaDataVersion")
        element.append(self.get_protocol_element())

        # StudyEventDefs (order among them is free; schedule carried by Alias)
        for model in self.get_common_models():
            element.append(self.get_common_event_def_element(model))
        for schedule in self.visit_schedule.schedules.values():
            for visit in schedule.visits.values():
                element.append(self.get_scheduled_def_element(visit, schedule.name))
            for visit in schedule.visits.values():
                if visit.crfs_unscheduled:
                    element.append(self.get_unscheduled_def_element(visit, schedule.name))

        # Shared, deduped definition catalog (CRF + requisition models the
        # events reference, plus common models), in ODM type order.
        # Skip abstract/unregistered models (e.g. an abstract death_report_model).
        form_models = {
            crf.model
            for schedule in self.visit_schedule.schedules.values()
            for visit in schedule.visits.values()
            for crf in [*visit.all_crfs, *visit.all_requisitions]
        }
        models = [
            m
            for m in dict.fromkeys([*self.get_common_models(), *sorted(form_models)])
            if self._model_exists(m)
        ]
        for model in models:
            element.append(self.get_form_def_element(model))
        for model in models:
            element.extend(self.get_item_group_defs_elements(model))
        for model in models:
            element.extend(self.get_item_defs_elements(model))
        for model in models:
            element.extend(self.get_codelist_elements(model))
        return element

    def get_protocol_element(self) -> etree._Element:
        element = etree.Element("Protocol")
        for schedule in self.visit_schedule.schedules.values():
            for visit in schedule.visits.values():
                etree.SubElement(
                    element,
                    "StudyEventRef",
                    StudyEventOID=self.scheduled_event_oid(visit.code),
                    Mandatory=YES,
                )
        for visit_code in self.get_crfs_unscheduled():
            etree.SubElement(
                element,
                "StudyEventRef",
                StudyEventOID=self.unscheduled_event_oid(visit_code),
                Mandatory=NO,
            )
        for model in self.get_common_models():
            etree.SubElement(
                element,
                "StudyEventRef",
                StudyEventOID=self.common_event_oid(model),
                Mandatory=NO,
            )
        return element

    @staticmethod
    def append_schedule_alias(element: etree._Element, schedule_name: str) -> None:
        etree.SubElement(element, "Alias", Context="clinicedc.schedule", Name=schedule_name)

    @staticmethod
    def get_form_def_element(model: str) -> etree._Element:
        model_cls = django_apps.get_model(model)
        fieldsets = get_modeladmin_fieldsets(model_cls)
        element = etree.Element(
            "FormDef",
            OID=oid(FORM, model),
            Name=str(model_cls._meta.verbose_name),
            Repeating=NO,
        )
        for index, (name, _options) in enumerate(fieldsets, start=1):
            section_key = fieldset_key(model, name, index)
            etree.SubElement(
                element,
                "ItemGroupRef",
                ItemGroupOID=oid(ITEM_GROUP, section_key),
                OrderNumber=str(index),
                Mandatory=YES,
            )
        return element

    @staticmethod
    def get_item_group_defs_elements(model: str) -> list[etree._Element]:
        elements = []
        model_cls = django_apps.get_model(model)
        fieldsets = get_modeladmin_fieldsets(model_cls)
        for index, (name, opts) in enumerate(fieldsets, start=1):
            section_key = fieldset_key(model, name, index)
            section_name = str(name) if name else str(model_cls._meta.verbose_name)
            element = etree.Element(
                "ItemGroupDef",
                OID=oid(ITEM_GROUP, section_key),
                Name=section_name,
                Repeating=NO,
            )
            for i, field_name in enumerate(opts.get("fields"), start=1):
                field = model_cls._meta.get_field(field_name)
                # TODO: need these fields! allow fk/uuid as text for now
                # TODO: M2M??
                # if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                #     continue
                etree.SubElement(
                    element,
                    "ItemRef",
                    ItemOID=oid(ITEM, f"{model}.{field.name}"),
                    OrderNumber=str(i),
                    Mandatory=YES if not field.blank else NO,
                )
            elements.append(element)
        return elements

    @staticmethod
    def get_item_defs_elements(model: str) -> list[etree._Element]:
        elements = []
        model_cls = django_apps.get_model(model)
        for field in iter_fieldset_fields(model_cls):
            opts: dict[str, str] = {
                "OID": oid(ITEM, f"{model}.{field.name}"),
                "Name": field.name,
                "DataType": get_odm_datatype(field),
            }
            if hasattr(field, "max_length") and field.max_length:
                opts["Length"] = str(field.max_length)
            element = etree.Element("ItemDef", **opts)
            desc = etree.SubElement(element, "Description")
            tt = etree.SubElement(desc, "TranslatedText")
            tt.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
            tt.text = str(field.verbose_name) or field.name
            if hasattr(field, "choices") and field.choices:
                codelist_oid = oid(CODELIST, f"{model}.{field.name}")
                etree.SubElement(element, "CodeListRef", CodeListOID=codelist_oid)
            elements.append(element)
        return elements

    @staticmethod
    def get_codelist_elements(model: str) -> list[etree._Element]:
        # TODO: will need to include listmodels
        elements = []
        model_cls = django_apps.get_model(model)
        for field in iter_fieldset_fields(model_cls):
            if not hasattr(field, "choices") or not field.choices:
                continue
            element = etree.Element(
                "CodeList",
                OID=oid(CODELIST, f"{model}.{field.name}"),
                Name=f"{field.name} choices",
                DataType="text",
            )
            for value, display in field.choices:
                if isinstance(display, (list, tuple)):
                    for sub_value, sub_display in display:
                        item = etree.SubElement(
                            element, "CodeListItem", CodedValue=str(sub_value)
                        )
                        decode = etree.SubElement(item, "Decode")
                        tt = etree.SubElement(decode, "TranslatedText")
                        tt.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                        tt.text = str(sub_display)
                else:
                    item = etree.SubElement(element, "CodeListItem", CodedValue=str(value))
                    decode = etree.SubElement(item, "Decode")
                    tt = etree.SubElement(decode, "TranslatedText")
                    tt.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                    tt.text = str(display)
            elements.append(element)
        return elements

    def get_scheduled_def_element(self, visit: Visit, schedule_name: str) -> etree._Element:
        """Build study event definition.

        Assume natural order of CrfCollection is the actual order.
        """
        i, index = (0, 0)
        element = etree.Element(
            "StudyEventDef",
            OID=self.scheduled_event_oid(visit.code),
            Name=visit.title,
            Repeating=NO,
            Type=SCHEDULED_TYPE,
        )
        # append CRFs
        crfs = [*visit.crfs, *visit.crfs_missed]
        for i, crf in enumerate(crfs, start=1):
            etree.SubElement(
                element,
                "FormRef",
                FormOID=oid(FORM, crf.model),
                OrderNumber=str(i),
                Mandatory=YES if crf.required else NO,
            )
        # append PRNs
        index = i + 1
        for i, prn in enumerate(self.iter_remaining_prns(visit), start=index):
            etree.SubElement(
                element,
                "FormRef",
                FormOID=oid(FORM, prn.model),
                OrderNumber=str(i),
                Mandatory=NO,
            )
        self.append_schedule_alias(element, schedule_name)
        return element

    def get_unscheduled_def_element(self, visit: Visit, schedule_name: str) -> etree._Element:
        """Build study event definition.

        Assume natural order of CrfCollection is the actual order.
        """
        i, index = (0, 0)
        element = etree.Element(
            "StudyEventDef",
            OID=self.unscheduled_event_oid(visit.code),
            Name=visit.title,
            Repeating=YES,
            Type=UNSCHEDULED_TYPE,
        )
        for i, crf in enumerate(visit.crfs_unscheduled, start=1):
            etree.SubElement(
                element,
                "FormRef",
                FormOID=oid(FORM, crf.model),
                OrderNumber=str(i),
                Mandatory=YES if crf.required else NO,
            )
        # append PRNs
        index = i + 1
        for i, prn in enumerate(
            self.iter_remaining_prns(visit, exclude_unscheduled=True), start=index
        ):
            etree.SubElement(
                element,
                "FormRef",
                FormOID=oid(FORM, prn.model),
                OrderNumber=str(i),
                Mandatory=NO,
            )
        self.append_schedule_alias(element, schedule_name)
        return element

    def get_common_event_def_element(
        self,
        model: str,
    ) -> etree._Element:
        verbose_name = str(django_apps.get_model(model)._meta.verbose_name)
        element = etree.Element(
            "StudyEventDef",
            OID=self.common_event_oid(model),
            Name=verbose_name,
            Repeating=NO,
            Type=COMMON_TYPE,
        )
        etree.SubElement(
            element,
            "FormRef",
            FormOID=oid(FORM, model),
            Mandatory=YES,
        )
        return element

    def get_crfs_unscheduled(self) -> dict[str, tuple[Crf, ...]]:
        dct: dict[str, tuple[Crf, ...]] = {}
        for schedule in self.visit_schedule.schedules.values():
            for visit in schedule.visits.values():
                if visit.crfs_unscheduled:
                    # name = f"{visit.code}_unscheduled"
                    if visit.code in dct:
                        raise ProtocolSerializerError(
                            f"Key unexpectedly exists. Got {visit.code}."
                        )
                    dct[visit.code] = visit.crfs_unscheduled.forms
        return dct

    @staticmethod
    def iter_remaining_prns(
        visit: Visit,
        exclude_unscheduled: bool | None = None,
    ) -> Iterator[Crf]:
        """Yields a Crf object representing a PRN Form.

        Yields only those that appear in crfs_prn but not in crfs.
        """
        if exclude_unscheduled:
            exclude = [f.model for f in visit.crfs_unscheduled.forms]
        else:
            exclude = [f.model for f in visit.crfs.forms]

        seen = {*exclude}
        for prn in visit.crfs_prn or ():
            if prn.model not in seen:
                seen.add(prn.model)
                yield prn
