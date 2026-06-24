Clinical Data Export
====================

``ClinicalDataSerializer`` exports submitted CRF values as ODM
``<ClinicalData>`` XML.

The data is read **directly from the** ``SubjectVisit`` **model and the CRF
instances** linked to each visit — a CRF instance existing for a
``subject_visit`` is the source of truth that it was entered.  (There is no
dependency on the ``CrfMetadata`` layer.)

Usage
-----

.. code-block:: python

   from edc_cdisc.serializers import ClinicalDataSerializer

   xml_bytes = ClinicalDataSerializer(
       edc_module_name="meta_edc",
       visit_schedule=visit_schedule,
       subject_identifiers=["100-0001"],   # optional, None = all subjects
       include_nulls=False,                # optional
   ).to_xml()

Output structure
----------------

.. code-block:: text

   ODM
     ClinicalData  (StudyOID="S.<protocol>" MetaDataVersionOID="MDV.<fp>")
       SubjectData  (SubjectKey="<subject_identifier>")
         StudyEventData  (StudyEventOID="SE.<code>" | "UE.<code>" | "CE.<model>")
           FormData  (FormOID="F.<model>")
             ItemGroupData  (ItemGroupOID="IG.<section>")
               ItemData  (ItemOID="I.<model>.<field>" Value="…")

``ClinicalData`` references the metadata by OID (``StudyOID`` and
``MetaDataVersionOID``) rather than nesting it — so a data file links to the
metadata edition it conforms to.  The ``MetaDataVersionOID`` is the same
``MDV.<fingerprint>`` the metadata serializer stamps.

Study events
~~~~~~~~~~~~

A subject's ``SubjectVisit`` rows map to ``StudyEventData`` by visit code and
sequence:

* ``visit_code_sequence == 0`` → scheduled → ``StudyEventOID="SE.<code>"``.
* ``visit_code_sequence > 0`` → unscheduled → ``StudyEventOID="UE.<code>"``
  with ``StudyEventRepeatKey="<sequence>"`` (unscheduled events repeat).
* Death-report / offstudy singletons → ``StudyEventOID="CE.<model>"``.

A **negative** ``visit_code_sequence`` raises ``NegativeVisitCodeSequenceError``
— it indicates corrupt state, and the export refuses to run rather than emit
a misleading file.

Null values
~~~~~~~~~~~

By default a null field is **omitted**, so each form instance contributes a
variable number of ``ItemData`` rows.  Pass ``include_nulls=True`` to emit
``<ItemData IsNull="Yes"/>`` for every null field instead — then every form
instance carries a fixed number of items, which makes record counts easy to
reconcile against the source tables.  Note that an empty string is *real*
(entered-but-blank) data and is always emitted as ``Value=""``; only ``None``
is treated as null.
