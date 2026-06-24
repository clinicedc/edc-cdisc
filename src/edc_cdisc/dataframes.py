# from __future__ import annotations
#
# from pathlib import Path
# from typing import TYPE_CHECKING
#
# from lxml import etree
#
# from .constants import ODM_NAMESPACE
#
# if TYPE_CHECKING:
#     import pandas as pd
#
# NS = {"odm": ODM_NAMESPACE}
#
# _PANDAS_MISSING = "pandas is required for this function. Install it with: pip install pandas"
#
#
# def _import_pandas():
#     try:
#         import pandas
#     except ImportError as e:
#         raise ImportError(_PANDAS_MISSING) from e
#     return pandas
#
#
# def odm_to_dataframe(
#     source: str | bytes | Path,
#     *,
#     long: bool = False,
# ) -> pd.DataFrame:
#     """Convert ODM ClinicalData XML to a pandas DataFrame.
#
#     Args:
#         source: XML bytes, a file path, or a string path.
#         long: If True, return long format (one row per ItemData).
#             If False (default), return wide format (one column per
#             ItemOID, one row per subject/event/form).
#     """
#     pandas = _import_pandas()
#
#     doc = _parse_source(source)
#     rows = _extract_item_rows(doc)
#     df = pandas.DataFrame(rows)
#
#     if df.empty:
#         cols = ["subject", "event", "form", "item_group", "item", "value"]
#         return pandas.DataFrame(columns=cols if long else ["subject", "event", "form"])
#
#     if long:
#         return df
#
#     return (
#         df.pivot_table(
#             index=["subject", "event", "form"],
#             columns="item",
#             values="value",
#             aggfunc="first",
#         )
#         .reset_index()
#         .rename_axis(columns=None)
#     )
#
#
# def odm_metadata_to_dataframe(
#     source: str | bytes | Path,
# ) -> dict[str, pd.DataFrame]:
#     """Extract ODM Study metadata into DataFrames.
#
#     Returns a dict with keys:
#         - "study_events": StudyEventDef elements
#         - "forms": FormDef elements
#         - "item_groups": ItemGroupDef elements
#         - "items": ItemDef elements
#         - "code_lists": CodeList/CodeListItem elements
#     """
#     pandas = _import_pandas()
#     doc = _parse_source(source)
#     return {
#         "study_events": _extract_study_events(doc, pandas),
#         "forms": _extract_forms(doc, pandas),
#         "item_groups": _extract_item_groups(doc, pandas),
#         "items": _extract_items(doc, pandas),
#         "code_lists": _extract_code_lists(doc, pandas),
#     }
#
#
# def _parse_source(source: str | bytes | Path) -> etree._Element:
#     if isinstance(source, bytes):
#         return etree.fromstring(source)
#     path = Path(source)
#     if path.exists():
#         return etree.parse(str(path)).getroot()
#     return etree.fromstring(source.encode())
#
#
# def _extract_item_rows(doc: etree._Element) -> list[dict[str, str | None]]:
#     rows: list[dict[str, str | None]] = []
#     for sd in doc.findall(".//odm:SubjectData", NS):
#         subj = sd.get("SubjectKey", "")
#         for se in sd.findall("odm:StudyEventData", NS):
#             event = se.get("StudyEventOID", "")
#             repeat_key = se.get("StudyEventRepeatKey", "")
#             event_key = f"{event}[{repeat_key}]" if repeat_key else event
#             for fd in se.findall("odm:FormData", NS):
#                 form = fd.get("FormOID", "")
#                 txn = fd.get("TransactionType", "")
#                 for ig in fd.findall("odm:ItemGroupData", NS):
#                     ig_oid = ig.get("ItemGroupOID", "")
#                     for item in ig.findall("odm:ItemData", NS):
#                         is_null = item.get("IsNull") == "Yes"
#                         row: dict[str, str | None] = {
#                             "subject": subj,
#                             "event": event_key,
#                             "form": form,
#                             "item_group": ig_oid,
#                             "item": item.get("ItemOID", ""),
#                             "value": None if is_null else item.get("Value", ""),
#                         }
#                         if txn:
#                             row["transaction_type"] = txn
#                         rows.append(row)
#     return rows
#
#
# def _extract_study_events(doc: etree._Element, pandas: object) -> pd.DataFrame:
#     rows = [
#         {
#             "OID": se.get("OID", ""),
#             "Name": se.get("Name", ""),
#             "Repeating": se.get("Repeating", ""),
#             "Type": se.get("Type", ""),
#         }
#         for se in doc.findall(".//odm:StudyEventDef", NS)
#     ]
#     return pandas.DataFrame(rows)
#
#
# def _extract_forms(doc: etree._Element, pandas: object) -> pd.DataFrame:
#     rows = [
#         {
#             "OID": fd.get("OID", ""),
#             "Name": fd.get("Name", ""),
#             "Repeating": fd.get("Repeating", ""),
#         }
#         for fd in doc.findall(".//odm:FormDef", NS)
#     ]
#     return pandas.DataFrame(rows)
#
#
# def _extract_item_groups(doc: etree._Element, pandas: object) -> pd.DataFrame:
#     rows = [
#         {
#             "OID": ig.get("OID", ""),
#             "Name": ig.get("Name", ""),
#             "Repeating": ig.get("Repeating", ""),
#         }
#         for ig in doc.findall(".//odm:ItemGroupDef", NS)
#     ]
#     return pandas.DataFrame(rows)
#
#
# def _extract_items(doc: etree._Element, pandas: object) -> pd.DataFrame:
#     rows = []
#     for item in doc.findall(".//odm:ItemDef", NS):
#         row = {
#             "OID": item.get("OID", ""),
#             "Name": item.get("Name", ""),
#             "DataType": item.get("DataType", ""),
#         }
#         cl_ref = item.find("odm:CodeListRef", NS)
#         if cl_ref is not None:
#             row["CodeListOID"] = cl_ref.get("CodeListOID", "")
#         rows.append(row)
#     return pandas.DataFrame(rows)
#
#
# def _extract_code_lists(doc: etree._Element, pandas: object) -> pd.DataFrame:
#     rows = []
#     for cl in doc.findall(".//odm:CodeList", NS):
#         cl_oid = cl.get("OID", "")
#         cl_name = cl.get("Name", "")
#         for cli in cl.findall("odm:CodeListItem", NS):
#             coded_value = cli.get("CodedValue", "")
#             decode_el = cli.find("odm:Decode/odm:TranslatedText", NS)
#             decode_text = decode_el.text if decode_el is not None and decode_el.text else ""
#             rows.append(
#                 {
#                     "CodeListOID": cl_oid,
#                     "CodeListName": cl_name,
#                     "CodedValue": coded_value,
#                     "Decode": decode_text,
#                 }
#             )
#     return pandas.DataFrame(rows)
