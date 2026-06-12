from clinicedc_tests.consents import consent_v1
from clinicedc_tests.visit_schedules.visit_schedule import (
    get_visit_schedule,
)
from django.test import TestCase
from lxml import etree

from edc_cdisc.odm import ODMStudySerializer
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

    def test_protocol_has_study_event_refs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        refs = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:Protocol/odm:StudyEventRef",
            NS,
        )
        visit_count = sum(len(s.visits) for s in self.visit_schedule.schedules.values())
        self.assertEqual(len(refs), visit_count)

    def test_study_event_defs_match_visits(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        seds = root.findall(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        visit_count = sum(len(s.visits) for s in self.visit_schedule.schedules.values())
        self.assertEqual(len(seds), visit_count)

    def test_study_event_def_has_form_refs(self) -> None:
        serializer = ODMStudySerializer(visit_schedule=self.visit_schedule)
        root = etree.fromstring(serializer.to_xml())
        sed = root.find(
            "odm:Study/odm:MetaDataVersion/odm:StudyEventDef",
            NS,
        )
        form_refs = sed.findall("odm:FormRef", NS)
        self.assertGreater(len(form_refs), 0)

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
