API Reference
=============

Serializers
-----------

.. module:: edc_cdisc.serializers

All serializers share a common constructor (keyword-only arguments) and the
``to_xml()`` / ``to_etree()`` output methods.

Common constructor arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Argument
     - Default
     - Meaning
   * - ``edc_module_name``
     - *(required)*
     - EDC project package (e.g. ``"meta_edc"``); used for the ODM
       ``SourceSystem`` / ``SourceSystemVersion`` header.
   * - ``visit_schedule``
     - *(required)*
     - The clinicedc ``VisitSchedule`` to export.
   * - ``subject_identifiers``
     - ``None``
     - Restrict to specific subjects (``None`` = all).  Data serializers only.
   * - ``include_nulls``
     - ``False``
     - Emit ``<ItemData IsNull="Yes"/>`` for null fields.  Data serializers
       only.
   * - ``protocol_oid``
     - ``S.<protocol>``
     - OID for the ``Study`` / ``ClinicalData``.
   * - ``protocol_name`` / ``protocol_title`` / ``protocol_number``
     - from ``ResearchProtocolConfig``
     - ``GlobalVariables`` text.
   * - ``file_type``
     - ``"Snapshot"``
     - ODM ``FileType`` header attribute.

Output methods
~~~~~~~~~~~~~~

.. method:: to_xml() -> bytes

   Serialize to UTF-8 XML bytes (XML declaration, pretty-printed).

.. method:: to_etree() -> lxml.etree._Element

   Return the root ``<ODM>`` element.

Classes
~~~~~~~

.. class:: MetadataSerializer

   Exports ``<ODM><Study>…</Study></ODM>`` — ``GlobalVariables`` plus a
   ``MetaDataVersion`` (``Protocol``, ``StudyEventDef``\s, ``FormDef``\s,
   ``ItemGroupDef``\s, ``ItemDef``\s, ``CodeList``\s).  The
   ``MetaDataVersion`` OID is a content fingerprint (``MDV.<sha>``).

.. class:: ClinicalDataSerializer

   Exports ``<ODM><ClinicalData>…</ClinicalData></ODM>`` from ``SubjectVisit``
   + CRF instances.  ``ClinicalData`` carries ``StudyOID`` and
   ``MetaDataVersionOID`` referencing the metadata edition.

.. class:: SnapshotSerializer

   Exports a combined ``<ODM><Study>…</Study><ClinicalData>…</ClinicalData></ODM>``
   by composing ``MetadataSerializer`` and ``ClinicalDataSerializer``.

.. class:: Serializer
.. class:: VisitScheduleSerializer

   Base classes.  ``Serializer`` builds the ``<ODM>`` root and
   ``GlobalVariables``; ``VisitScheduleSerializer`` adds ``visit_schedule``,
   ``subject_identifiers``, ``include_nulls``, the event-OID helpers, and
   ``get_common_models``.


Validation
----------

.. module:: edc_cdisc

.. function:: validate_odm(doc) -> list[str]

   Validate an ODM document against the bundled ODM 1.3.1 XSD and check OID
   reference integrity.

   :param doc: XML ``bytes`` or an lxml element.
   :returns: a list of problem strings (``"XSD line <n>: <msg>"`` or
       ``"dangling ref: <oid>"``); empty list means valid and internally
       consistent.

   See :doc:`validation`.


Exceptions
----------

.. module:: edc_cdisc.exceptions

.. exception:: NegativeVisitCodeSequenceError

   Raised by ``ClinicalDataSerializer`` when a ``SubjectVisit`` has a negative
   ``visit_code_sequence`` (corrupt state).

.. exception:: ModelAdminNotFoundError

   Raised when a CRF model in the visit schedule has no registered
   ``ModelAdmin``.
