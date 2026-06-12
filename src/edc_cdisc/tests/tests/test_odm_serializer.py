from clinicedc_tests.consents import consent_v1
from clinicedc_tests.visit_schedules.visit_schedule import (
    get_visit_schedule,
)
from django.test import TestCase
from edc_visit_schedule.visit import Crf, CrfCollection
from lxml import etree

from edc_cdisc.odm import ODMStudySerializer
from edc_cdisc.odm.builders import collect_common_models
from edc_cdisc.odm.constants import ODM_NAMESPACE, ODM_VERSION

NS = {"odm": ODM_NAMESPACE}


class TestODMStudySerializer(TestCase):
    def setUp(self) -> None:
        self.visit_schedule = get_visit_schedule(consent_v1)

    def test_to_xml_returns_bytes(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        result = serializer.to_xml()
        self.assertIsInstance(result, bytes)

    def test_xml_is_well_formed(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        self.assertEqual(root.tag, f"{{{ODM_NAMESPACE}}}ODM")

    def test_odm_version(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        self.assertEqual(root.get("ODMVersion"), ODM_VERSION)

    def test_file_type(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        self.assertEqual(root.get("FileType"), "Snapshot")

    def test_study_element_exists(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        studies = root.findall("odm:Study", NS)
        self.assertEqual(len(studies), 1)

    def test_global_variables(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        gv = root.find("odm:Study/odm:GlobalVariables", NS)
        self.assertIsNotNone(gv)
        study_name = gv.find("odm:StudyName", NS)
        self.assertIsNotNone(study_name)
        self.assertTrue(len(study_name.text) > 0)

    def test_metadata_version(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        mdv = root.find("odm:Study/odm:MetaDataVersion", NS)
        self.assertIsNotNone(mdv)
        self.assertEqual(mdv.get("OID"), "MDV.1")

    def test_protocol_has_scheduled_event_refs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        refs = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:Protocol/odm:StudyEventRef",
            NS,
        )
        scheduled_refs = [
            r
            for r in refs
            if not r.get("StudyEventOID", "").startswith("SE.UNSCHED.")
            and not r.get("StudyEventOID", "").startswith("SE.COMMON.")
        ]
        visit_count = sum(len(s.visits) for s in self.visit_schedule.schedules.values())
        self.assertEqual(len(scheduled_refs), visit_count)

    def test_protocol_has_unscheduled_event_refs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        refs = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:Protocol/odm:StudyEventRef",
            NS,
        )
        unsched_refs = [
            r for r in refs if r.get("StudyEventOID", "").startswith("SE.UNSCHED.")
        ]
        self.assertGreater(len(unsched_refs), 0)
        for ref in unsched_refs:
            self.assertEqual(ref.get("Mandatory"), "No")

    def test_protocol_has_common_event_refs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        refs = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:Protocol/odm:StudyEventRef",
            NS,
        )
        common_refs = [r for r in refs if r.get("StudyEventOID", "").startswith("SE.COMMON.")]
        self.assertGreater(len(common_refs), 0)
        for ref in common_refs:
            self.assertEqual(ref.get("Mandatory"), "No")

    def test_scheduled_study_event_defs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        seds = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        scheduled = [s for s in seds if s.get("Type") == "Scheduled"]
        visit_count = sum(len(s.visits) for s in self.visit_schedule.schedules.values())
        self.assertEqual(len(scheduled), visit_count)

    def test_unscheduled_study_event_defs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        seds = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        unscheduled = [s for s in seds if s.get("Type") == "Unscheduled"]
        self.assertGreater(len(unscheduled), 0)
        for sed in unscheduled:
            self.assertEqual(sed.get("Repeating"), "Yes")

    def test_common_study_event_defs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        seds = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        common = [s for s in seds if s.get("Type") == "Common"]
        self.assertGreater(len(common), 0)

    def test_common_event_offstudy(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        seds = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        offstudy_events = [
            s for s in seds if "edc_offstudy.subjectoffstudy" in s.get("OID", "")
        ]
        self.assertEqual(len(offstudy_events), 1)
        self.assertEqual(offstudy_events[0].get("Type"), "Common")

    def test_common_event_skips_unresolvable_model(self) -> None:
        models = collect_common_models(self.visit_schedule)
        self.assertNotIn("edc_adverse_event.deathreport", models)
        self.assertIn("edc_offstudy.subjectoffstudy", models)

    def test_study_event_def_has_form_refs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        sed = root.find(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        form_refs = sed.findall("odm:FormRef", NS)
        self.assertGreater(len(form_refs), 0)

    def test_prn_crfs_included_in_study_event_def(self) -> None:
        crfs_prn = CrfCollection(
            Crf(show_order=100, model="clinicedc_tests.crfone"),
            Crf(show_order=101, model="clinicedc_tests.crftwo"),
            name="prn",
        )
        visit_schedule = get_visit_schedule(
            consent_v1,
            crfs=CrfCollection(
                Crf(show_order=1, model="clinicedc_tests.crflongitudinalone"),
                Crf(show_order=2, model="clinicedc_tests.crflongitudinaltwo"),
            ),
        )
        for schedule in visit_schedule.schedules.values():
            for visit in schedule.visits.values():
                visit._crfs_prn = crfs_prn
                visit.crfs_prn = crfs_prn

        serializer = ODMStudySerializer(visit_schedule=visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        sed = root.find(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        form_refs = sed.findall("odm:FormRef", NS)
        oids = [ref.get("FormOID") for ref in form_refs]
        self.assertIn("F.clinicedc_tests.crfone", oids)
        self.assertIn("F.clinicedc_tests.crftwo", oids)

    def test_prn_form_refs_mandatory_no(self) -> None:
        crfs_prn = CrfCollection(
            Crf(show_order=100, model="clinicedc_tests.crfone"),
            name="prn",
        )
        visit_schedule = get_visit_schedule(
            consent_v1,
            crfs=CrfCollection(
                Crf(show_order=1, model="clinicedc_tests.crflongitudinalone"),
            ),
        )
        for schedule in visit_schedule.schedules.values():
            for visit in schedule.visits.values():
                visit.crfs_prn = crfs_prn

        serializer = ODMStudySerializer(visit_schedule=visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        sed = root.find(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        prn_ref = [
            ref
            for ref in sed.findall("odm:FormRef", NS)
            if ref.get("FormOID") == "F.clinicedc_tests.crfone"
        ]
        self.assertEqual(len(prn_ref), 1)
        self.assertEqual(prn_ref[0].get("Mandatory"), "No")

    def test_prn_crfs_not_duplicated_when_already_scheduled(self) -> None:
        crfs = CrfCollection(
            Crf(show_order=1, model="clinicedc_tests.crflongitudinalone"),
        )
        crfs_prn = CrfCollection(
            Crf(show_order=100, model="clinicedc_tests.crflongitudinalone"),
            name="prn",
        )
        visit_schedule = get_visit_schedule(consent_v1, crfs=crfs)
        for schedule in visit_schedule.schedules.values():
            for visit in schedule.visits.values():
                visit.crfs_prn = crfs_prn

        serializer = ODMStudySerializer(visit_schedule=visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        sed = root.find(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        matching = [
            ref
            for ref in sed.findall("odm:FormRef", NS)
            if ref.get("FormOID") == "F.clinicedc_tests.crflongitudinalone"
        ]
        self.assertEqual(len(matching), 1)

    def test_unscheduled_event_has_form_refs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        seds = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        unscheduled = [s for s in seds if s.get("Type") == "Unscheduled"]
        for sed in unscheduled:
            form_refs = sed.findall("odm:FormRef", NS)
            self.assertGreater(len(form_refs), 0)

    def test_unscheduled_models_in_form_defs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        fds = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:FormDef",
            NS,
        )
        form_oids = {fd.get("OID") for fd in fds}
        self.assertIn("F.clinicedc_tests.crfeight", form_oids)

    def test_common_models_in_form_defs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        fds = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:FormDef",
            NS,
        )
        form_oids = {fd.get("OID") for fd in fds}
        self.assertIn("F.edc_offstudy.subjectoffstudy", form_oids)

    def test_form_defs_exist(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        fds = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:FormDef",
            NS,
        )
        self.assertGreater(len(fds), 0)

    def test_item_group_defs_exist(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        igds = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:ItemGroupDef",
            NS,
        )
        self.assertGreater(len(igds), 0)

    def test_item_defs_exist(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        items = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:ItemDef",
            NS,
        )
        self.assertGreater(len(items), 0)

    def test_item_def_has_datatype(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        item = root.find(
            "odm:Study/odm:MetaDataVersion/odm:ItemDef",
            NS,
        )
        self.assertIn(
            item.get("DataType"),
            [
                "text",
                "integer",
                "float",
                "date",
                "datetime",
                "time",
                "boolean",
                "URI",
                "hexBinary",
            ],
        )

    def test_code_lists_for_choice_fields(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        cls = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:CodeList",
            NS,
        )
        self.assertGreater(len(cls), 0)

    def test_code_list_has_items(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        cl = root.find(
            "odm:Study/odm:MetaDataVersion/odm:CodeList",
            NS,
        )
        items = cl.findall("odm:CodeListItem", NS)
        self.assertGreater(len(items), 0)

    def test_custom_study_oid(self) -> None:
        serializer = ODMStudySerializer(
            visit_schedule=self.visit_schedule,
            study_oid="S.CUSTOM",
        )
        root = etree.fromstring(serializer.to_xml())
        study = root.find("odm:Study", NS)
        self.assertEqual(study.get("OID"), "S.CUSTOM")

    def test_custom_metadata_version(self) -> None:
        serializer = ODMStudySerializer(
            visit_schedule=self.visit_schedule,
            metadata_version_oid="MDV.2",
            metadata_version_name="Version 2",
        )
        root = etree.fromstring(serializer.to_xml())
        mdv = root.find("odm:Study/odm:MetaDataVersion", NS)
        self.assertEqual(mdv.get("OID"), "MDV.2")
        self.assertEqual(mdv.get("Name"), "Version 2")

    def test_to_etree_returns_element(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = serializer.to_etree()
        self.assertIsInstance(root, etree._Element)

    def test_form_ref_mandatory_matches_crf_required(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        seds = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        for sed in seds:
            for form_ref in sed.findall("odm:FormRef", NS):
                mandatory = form_ref.get("Mandatory")
                self.assertIn(mandatory, ["Yes", "No"])

    def test_originator(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        self.assertEqual(root.get("Originator"), "clinicedc/edc-cdisc")
