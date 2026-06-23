from __future__ import annotations

from lxml import etree


def build_crf_data_element(
    protocol_oid: str,
    metadata_version_oid: str,
    subject_longitudinal_data: list[etree._Element],
) -> etree._Element:
    cd = etree.Element(
        "ClinicalData",
        StudyOID=protocol_oid,
        MetaDataVersionOID=metadata_version_oid,
    )
    for data in subject_longitudinal_data:
        cd.append(data)
    return cd
