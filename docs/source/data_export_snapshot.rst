Data Export --- Snapshot
========================

``ODMClinicalDataSerializer`` exports all submitted CRF data as an ODM
``ClinicalData`` element with ``FileType="Snapshot"``.  A snapshot is a
complete point-in-time extract: every enrolled subject, every completed visit,
and every submitted CRF.

Usage
-----

.. code-block:: python

   from edc_cdisc.odm import ODMClinicalDataSerializer

   serializer = ODMClinicalDataSerializer(
       visit_schedule=visit_schedule,
       subject_identifiers=None,      # optional: filter to specific subjects
       study_oid="S.EFFECT",          # optional, defaults to protocol name
       metadata_version_oid="MDV.1",  # optional
   )
   xml_bytes = serializer.to_xml()

How it works
------------

1. **Subjects** --- All ``SubjectVisit`` records for the visit schedule are
   queried, grouped by ``subject_identifier``.  If ``subject_identifiers`` is
   provided, only those subjects are included.

2. **Visits** --- For each subject, visits are iterated in order of
   ``visit_code`` and ``visit_code_sequence``.

3. **CRFs** --- For each visit, ``CrfMetadata`` records with
   ``entry_status="KEYED"`` are queried.  The corresponding model instance
   (``metadata.model_instance``) is loaded for each.

4. **Fields** --- CRF fields are read using the ``ModelAdmin`` fieldsets (if
   registered) or ``Model._meta.get_fields()`` as a fallback.  Each field value
   is serialized to a string representation suitable for ODM.

5. **Empty visits** --- Visits with no submitted CRFs are omitted from the
   output (no empty ``StudyEventData`` elements).

Output structure
----------------

.. code-block:: text

   ODM (FileType="Snapshot")
     ClinicalData (StudyOID, MetaDataVersionOID)
       SubjectData (SubjectKey=subject_identifier)
         StudyEventData (StudyEventOID="SE.<visit_code>")
           FormData (FormOID="F.<app_label>.<model_name>")
             ItemGroupData (ItemGroupOID="IG.<section_key>")
               ItemData (ItemOID="I.<app_label>.<model_name>.<field>", Value="...")
               ItemData ...
             ItemGroupData ...
           FormData ...
         StudyEventData ...
       SubjectData ...

Unscheduled visits
~~~~~~~~~~~~~~~~~~

Unscheduled visits (``visit_code_sequence > 0``) include a
``StudyEventRepeatKey`` attribute on their ``StudyEventData`` element, as
required by the ODM specification for repeating events.

Value serialization
-------------------

Python values are converted to ODM-compatible strings by ``serialize_value()``:

=================  ==========================  =========================
Python type        Example input               ODM string
=================  ==========================  =========================
``bool``           ``True``                    ``"true"``
``datetime``       ``2025-08-11T08:00:00+00``  ``"2025-08-11T08:00:00+00:00"``
``date``           ``date(2025, 8, 11)``       ``"2025-08-11"``
``time``           ``time(14, 30)``            ``"14:30:00"``
``Decimal``        ``Decimal("1.5")``          ``"1.5"``
``float``          ``3.14``                    ``"3.14"``
``int``            ``42``                      ``"42"``
``UUID``           ``UUID("abcd...")``         ``"abcd..."``
``str``            ``"hello"``                 ``"hello"``
``None``           ``None``                    *(omitted)*
=================  ==========================  =========================

Fields with a ``None`` value are excluded from the output entirely (no
``ItemData`` element is emitted).
