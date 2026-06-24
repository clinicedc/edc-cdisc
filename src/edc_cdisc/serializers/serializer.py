from __future__ import annotations

from datetime import UTC, datetime
from functools import cached_property
from importlib.metadata import version

from edc_protocol.research_protocol_config import ResearchProtocolConfig
from lxml import etree

from ..constants import NSMAP, ODM_VERSION


class Serializer:
    protocol_config: ResearchProtocolConfig = ResearchProtocolConfig()

    def __init__(
        self,
        *,
        edc_module_name: str,
        protocol_oid: str | None = None,
        protocol_name: str | None = None,
        protocol_title: str | None = None,
        protocol_number: str | None = None,
        tostring_method: str | None = None,
        file_type: str | None = None,
    ):
        self.edc_module_name = edc_module_name
        self.now = datetime.now(tz=UTC).isoformat()
        self.protocol_oid = protocol_oid or f"S.{self.protocol_config.protocol}"
        self.protocol_name = protocol_name or self.protocol_config.protocol_name
        self.protocol_number = protocol_number or self.protocol_config.protocol_number
        self.protocol_title = protocol_title or self.protocol_config.protocol_title
        self.tostring_method = tostring_method or "xml"
        self.file_type = file_type or "Snapshot"

    def to_xml(self) -> bytes:
        return etree.tostring(
            self.to_etree(),
            xml_declaration=True,
            encoding="UTF-8",
            method=self.tostring_method,
            pretty_print=True,
        )

    def to_etree(self) -> etree._Element:
        return self.root_element

    @cached_property
    def metadata_version(self) -> str:
        return version(self.edc_module_name)

    @property
    def metadata_version_name(self) -> str:
        return f"revision {self.metadata_version}"

    @property
    def root_element(self) -> etree._Element:
        return etree.Element(
            "ODM",
            nsmap=NSMAP,
            FileOID=f"{self.protocol_oid}.ODM.{self.now}",
            FileType=self.file_type,
            CreationDateTime=self.now,
            ODMVersion=ODM_VERSION,
            Originator=self.protocol_config.institution,
            SourceSystem=self.edc_module_name,
            SourceSystemVersion=self.metadata_version,
        )

    @property
    def global_variables(self) -> etree._Element:
        gv = etree.Element("GlobalVariables")
        etree.SubElement(gv, "StudyName").text = self.protocol_name
        etree.SubElement(gv, "StudyDescription").text = self.protocol_title
        etree.SubElement(gv, "ProtocolName").text = self.protocol_name
        return gv
