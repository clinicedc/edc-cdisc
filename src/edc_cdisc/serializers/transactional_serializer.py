# from ..builders import build_crf_data_element
#
#
# @dataclass
# class ODMTransactionalSerializer:
#     """Export CRF data changed since a cutoff as ODM Transactional XML.
#
#     Each FormData element carries a TransactionType of "Insert" or
#     "Update" depending on whether the CRF was created or modified
#     after ``since``.
#     """
#
#     visit_schedule: VisitSchedule
#     since: datetime
#     subject_identifiers: Iterable[str] | None = None
#     protocol_oid: str = ""
#     metadata_version_oid: str = "MDV.1"
#     include_nulls: bool = False
#
#     _protocol_config: ResearchProtocolConfig = field(
#         init=False, repr=False, default_factory=ResearchProtocolConfig
#     )
#
#     def __post_init__(self) -> None:
#         if not self.protocol_oid:
#             self.protocol_oid = f"S.{self._protocol_config.protocol}"
#
#     def to_xml(self) -> bytes:
#         root = self.build_root()
#         clinical_data = self.build_clinical_data()
#         root.append(clinical_data)
#         return etree.tostring(
#             root,
#             xml_declaration=True,
#             encoding="UTF-8",
#             pretty_print=True,
#         )
#
#     def to_etree(self) -> etree._Element:
#         root = self.build_root()
#         crf_data = self.build_crf_data_for_all_subjects()
#         root.append(crf_data)
#         return root
#
#     def build_root(self) -> etree._Element:
#         now = datetime.now(tz=UTC).isoformat()
#         return etree.Element(
#             "ODM",
#             nsmap=NSMAP,
#             FileOID=f"{self.protocol_oid}.ODM.{now}",
#             FileType="Transactional",
#             CreationDateTime=now,
#             ODMVersion=ODM_VERSION,
#             Originator="clinicedc/edc-cdisc",
#         )
#
#     def build_crf_data_for_all_subjects(self) -> etree._Element:
#         related_visits_qs = get_related_visits(
#             visit_schedule=self.visit_schedule,
#             subject_identifiers=self.subject_identifiers,
#         )
#         subject_identifiers = related_visits_qs.values_list(
#             "subject_identifier", flat=True
#         ).distinct()
#         subject_longitudinal_data: list[etree._Element] = []
#         for subject_identifier in tqdm(
#             subject_identifiers, desc="Transactional", unit="subject"
#         ):
#             crf_data = self.build_crf_data_for_one_subject(
#                 subject_identifier,
#                 related_visits_qs.filter(subject_identifier=subject_identifier),
#             )
#             if crf_data:
#                 subject_longitudinal_data.append(crf_data)
#
#         return build_crf_data_element(
#             protocol_oid=self.protocol_oid,
#             metadata_version_oid=self.metadata_version_oid,
#             subject_longitudinal_data=subject_longitudinal_data,
#         )
#
#     def build_crf_data_for_one_subject(
#         self,
#         subject_identifier: str,
#         visits: list | QuerySet,
#     ) -> etree._Element | None:
#         study_event_elements: list[etree._Element] = []
#         for visit in visits:
#             crf_metadata_qs = get_crf_metadata_model_cls().objects.filter(
#                 subject_identifier=subject_identifier,
#                 visit_code=visit.visit_code,
#                 visit_code_sequence=visit.visit_code_sequence,
#                 visit_schedule_name=visit.visit_schedule_name,
#                 schedule_name=visit.schedule_name,
#                 entry_status=KEYED,
#             )
#             changed = get_changed_crf_instances(crf_metadata_qs, since=self.since)
#             form_data_elements = [
#                 build_form_data(
#                     model_label,
#                     instance,
#                     transaction_type=txn_type,
#                     include_nulls=self.include_nulls,
#                 )
#                 for model_label, instance, txn_type in changed
#             ]
#             if form_data_elements:
#                 study_event_elements.append(
#                     build_study_event_data(
#                         visit_code=visit.visit_code,
#                         visit_code_sequence=visit.visit_code_sequence,
#                         form_data_elements=form_data_elements,
#                     )
#                 )
#         if not study_event_elements:
#             return None
#         return append_to_subjectdata_element_for_subject(
#             subject_identifier=subject_identifier,
#             study_event_elements=study_event_elements,
#         )
