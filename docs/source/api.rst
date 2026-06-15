API Reference
=============

Serializers
-----------

.. module:: edc_cdisc.odm

ODMStudySerializer
~~~~~~~~~~~~~~~~~~

.. class:: ODMStudySerializer(visit_schedule, study_oid="", study_name="", study_description="", metadata_version_oid="MDV.1", metadata_version_name="Version 1")

   Export study metadata (visit schedule, CRF definitions, field definitions,
   code lists) as ODM 1.3.1 XML with ``FileType="Snapshot"``.

   :param visit_schedule: The clinicedc ``VisitSchedule`` instance to export.
   :type visit_schedule: edc_visit_schedule.visit_schedule.VisitSchedule
   :param study_oid: OID for the Study element.  Defaults to
       ``S.<protocol_name>`` from ``ResearchProtocolConfig``.
   :type study_oid: str
   :param study_name: Human-readable study name.  Defaults to
       ``ResearchProtocolConfig.project_name``.
   :type study_name: str
   :param study_description: Free-text description for ``GlobalVariables``.
   :type study_description: str
   :param metadata_version_oid: OID for the ``MetaDataVersion`` element.
   :type metadata_version_oid: str
   :param metadata_version_name: Display name for the ``MetaDataVersion``.
   :type metadata_version_name: str

   .. method:: to_xml() -> bytes

      Serialize to UTF-8 XML bytes with XML declaration and pretty-printing.

   .. method:: to_etree() -> lxml.etree._Element

      Return the root ``ODM`` element as an lxml Element tree.

ODMClinicalDataSerializer
~~~~~~~~~~~~~~~~~~~~~~~~~

.. class:: ODMClinicalDataSerializer(visit_schedule, subject_identifiers=None, study_oid="", metadata_version_oid="MDV.1", include_nulls=False)

   Export all submitted CRF data as ODM 1.3.1 ``ClinicalData`` XML with
   ``FileType="Snapshot"``.

   :param visit_schedule: The clinicedc ``VisitSchedule`` instance.
   :type visit_schedule: edc_visit_schedule.visit_schedule.VisitSchedule
   :param subject_identifiers: Optional iterable of subject identifiers to
       include.  ``None`` means all subjects.
   :type subject_identifiers: Iterable[str] | None
   :param study_oid: OID for the ``ClinicalData`` element.  Defaults to
       ``S.<protocol_name>``.
   :type study_oid: str
   :param metadata_version_oid: OID for the ``MetaDataVersionOID`` attribute.
   :type metadata_version_oid: str
   :param include_nulls: When ``True``, null fields are emitted as
       ``<ItemData IsNull="Yes"/>`` instead of being omitted, so every
       form instance carries a fixed number of ``ItemData`` children.
       Defaults to ``False`` (sparse output).
   :type include_nulls: bool

   .. method:: to_xml() -> bytes

      Serialize to UTF-8 XML bytes.

   .. method:: to_etree() -> lxml.etree._Element

      Return the root ``ODM`` element as an lxml Element tree.

ODMSnapshotSerializer
~~~~~~~~~~~~~~~~~~~~~

.. class:: ODMSnapshotSerializer(visit_schedule, subject_identifiers=None, study_oid="", study_name="", study_description="", metadata_version_oid="MDV.1", metadata_version_name="Version 1", include_nulls=False)

   Combined Snapshot: export study metadata (``<Study>``) and clinical data
   (``<ClinicalData>``) in a single ODM 1.3.1 file with
   ``FileType="Snapshot"``.

   :param visit_schedule: The clinicedc ``VisitSchedule`` instance.
   :type visit_schedule: edc_visit_schedule.visit_schedule.VisitSchedule
   :param subject_identifiers: Optional iterable of subject identifiers to
       include.  ``None`` means all subjects.
   :type subject_identifiers: Iterable[str] | None
   :param study_oid: OID for the ``Study`` and ``ClinicalData`` elements.
       Defaults to ``S.<protocol_name>``.
   :type study_oid: str
   :param study_name: Human-readable study name.  Defaults to
       ``ResearchProtocolConfig.project_name``.
   :type study_name: str
   :param study_description: Free-text description for ``GlobalVariables``.
   :type study_description: str
   :param metadata_version_oid: OID for the ``MetaDataVersion`` element and
       ``ClinicalData.MetaDataVersionOID``.
   :type metadata_version_oid: str
   :param metadata_version_name: Display name for the ``MetaDataVersion``.
   :type metadata_version_name: str
   :param include_nulls: When ``True``, null fields are emitted as
       ``<ItemData IsNull="Yes"/>`` instead of being omitted.  Defaults to
       ``False``.
   :type include_nulls: bool

   .. method:: to_xml() -> bytes

      Serialize to UTF-8 XML bytes.

   .. method:: to_etree() -> lxml.etree._Element

      Return the root ``ODM`` element as an lxml Element tree.

ODMTransactionalSerializer
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. class:: ODMTransactionalSerializer(visit_schedule, since, subject_identifiers=None, study_oid="", metadata_version_oid="MDV.1", include_nulls=False)

   Export CRF data changed since a cutoff timestamp as ODM 1.3.1
   ``ClinicalData`` XML with ``FileType="Transactional"``.

   Each ``FormData`` element carries a ``TransactionType`` of ``"Insert"``
   (created after ``since``) or ``"Update"`` (modified after ``since``).
   Subjects and visits with no changes are omitted.

   :param visit_schedule: The clinicedc ``VisitSchedule`` instance.
   :type visit_schedule: edc_visit_schedule.visit_schedule.VisitSchedule
   :param since: Export CRFs created or modified on or after this timestamp.
   :type since: datetime.datetime
   :param subject_identifiers: Optional iterable of subject identifiers.
   :type subject_identifiers: Iterable[str] | None
   :param study_oid: OID for the ``ClinicalData`` element.
   :type study_oid: str
   :param metadata_version_oid: OID for the ``MetaDataVersionOID`` attribute.
   :type metadata_version_oid: str
   :param include_nulls: When ``True``, null fields are emitted as
       ``<ItemData IsNull="Yes"/>`` instead of being omitted.  Defaults to
       ``False``.
   :type include_nulls: bool

   .. method:: to_xml() -> bytes

      Serialize to UTF-8 XML bytes.

   .. method:: to_etree() -> lxml.etree._Element

      Return the root ``ODM`` element as an lxml Element tree.


DataFrame utilities
-------------------

.. module:: edc_cdisc.odm.dataframes

.. function:: odm_to_dataframe(source, *, long=False) -> pandas.DataFrame

   Convert ODM ``ClinicalData`` XML to a pandas DataFrame.

   :param source: XML bytes, a file path (``str`` or ``Path``), or raw XML
       string.
   :type source: str | bytes | Path
   :param long: If ``True``, return long format (one row per ``ItemData``).
       If ``False`` (default), return wide format (one column per
       ``ItemOID``, one row per subject/event/form).
   :type long: bool
   :rtype: pandas.DataFrame

   In long format, the DataFrame has columns: ``subject``, ``event``,
   ``form``, ``item_group``, ``item``, ``value``.  Transactional XML adds
   a ``transaction_type`` column.

   In wide format, ``item`` values are pivoted into columns.

.. function:: odm_metadata_to_dataframe(source) -> dict[str, pandas.DataFrame]

   Extract ODM ``Study`` metadata into a dictionary of DataFrames.

   :param source: XML bytes, a file path, or raw XML string.
   :type source: str | bytes | Path
   :rtype: dict[str, pandas.DataFrame]

   Returns a dict with keys:

   * ``"study_events"`` --- columns: ``OID``, ``Name``, ``Repeating``, ``Type``
   * ``"forms"`` --- columns: ``OID``, ``Name``, ``Repeating``
   * ``"item_groups"`` --- columns: ``OID``, ``Name``, ``Repeating``
   * ``"items"`` --- columns: ``OID``, ``Name``, ``DataType``,
     ``CodeListOID`` (when applicable)
   * ``"code_lists"`` --- columns: ``CodeListOID``, ``CodeListName``,
     ``CodedValue``, ``Decode``


Builder functions
-----------------

.. module:: edc_cdisc.odm.clinical_data_builders

These are lower-level functions used by the serializers.  They can be called
directly for custom XML assembly.

.. function:: serialize_value(value) -> str | None

   Convert a Python value to an ODM-compatible string.  Returns ``None`` for
   ``None`` input (the caller should omit the ``ItemData`` element).

   :param value: Any Python value from a model field.
   :rtype: str | None

.. function:: build_clinical_data(study_oid, metadata_version_oid, subject_data_elements) -> lxml.etree._Element

   Build a ``ClinicalData`` element containing the given ``SubjectData``
   children.

.. function:: build_subject_data(subject_identifier, study_event_elements, transaction_type=None) -> lxml.etree._Element

   Build a ``SubjectData`` element.  If ``transaction_type`` is provided, it is
   set as the ``TransactionType`` attribute.

.. function:: build_study_event_data(visit_code, visit_code_sequence, form_data_elements, transaction_type=None) -> lxml.etree._Element

   Build a ``StudyEventData`` element.  Includes ``StudyEventRepeatKey`` if
   ``visit_code_sequence > 0``.

.. function:: build_form_data(model_label, instance, transaction_type=None) -> lxml.etree._Element

   Build a ``FormData`` element from a CRF model instance.  Reads fieldsets
   from the registered ``ModelAdmin`` or falls back to ``Model._meta`` fields.

.. function:: get_submitted_crf_instances(subject_identifier, visit_code, visit_code_sequence, visit_schedule_name, schedule_name) -> list[tuple[str, Model]]

   Query ``CrfMetadata`` for all CRFs with ``entry_status="KEYED"`` at a given
   visit.  Returns a list of ``(model_label, instance)`` tuples.

.. function:: get_changed_crf_instances(metadata_qs, since) -> list[tuple[str, Model, str]]

   Given a metadata queryset and a cutoff timestamp, return
   ``(model_label, instance, transaction_type)`` tuples for CRFs that have
   been created or modified since the cutoff.

.. function:: get_subject_visits(visit_schedule_name, subject_identifiers=None) -> QuerySet

   Return a ``SubjectVisit`` queryset for the given visit schedule, ordered by
   subject, visit code, and sequence.  Optionally filtered by subject
   identifiers.


Management commands
-------------------

``validate_odm_export``
~~~~~~~~~~~~~~~~~~~~~~~

Run all four export serializers against registered visit schedules, validate
against the ODM 1.3.1 XSD, and report statistics.

Options:

* ``--visit-schedule NAME`` --- validate a single visit schedule
* ``--since-days N`` --- transactional lookback in days (default: 30)
* ``--output-dir PATH`` --- write XML files for inspection
* ``--skip-xsd`` --- skip XSD validation

See :doc:`validation` for full usage examples.
