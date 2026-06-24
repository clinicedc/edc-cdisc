Metadata Export
===============

``MetadataSerializer`` exports the study definition as ODM XML — the
structural blueprint of the study (visit schedule, CRF forms, field
definitions, and code lists) without any subject data.

A receiving system uses this file to understand the shape of the data before
importing clinical records.

Usage
-----

.. code-block:: python

   from edc_cdisc.serializers import MetadataSerializer

   xml_bytes = MetadataSerializer(
       edc_module_name="meta_edc",
       visit_schedule=visit_schedule,
       protocol_oid="S.META",            # optional, defaults to S.<protocol>
       protocol_name="META Trial",       # optional
   ).to_xml()

Output structure
----------------

.. code-block:: text

   ODM
     Study  (OID="S.<protocol>")
       GlobalVariables
         StudyName / StudyDescription / ProtocolName
       MetaDataVersion  (OID="MDV.<fingerprint>")
         Protocol
           StudyEventRef ...        (scheduled / unscheduled / common)
         StudyEventDef ...          (one per scheduled visit, unscheduled
                                     collection, and common event)
           FormRef ...
           Alias  (Context="clinicedc.schedule")
         FormDef ...                (one per CRF / requisition / common model)
           ItemGroupRef ...
         ItemGroupDef ...           (one per admin fieldset section)
           ItemRef ...
         ItemDef ...                (one per field)
         CodeList ...               (choice fields)

Study events
~~~~~~~~~~~~

Each ``Visit`` produces a ``StudyEventDef``:

* **Scheduled** — ``OID="SE.<visit_code>"``, ``Type="Scheduled"``.  Its
  ``FormRef`` entries are the visit's CRFs (plus missed-visit and remaining
  PRN CRFs).
* **Unscheduled** — ``OID="UE.<visit_code>"``, ``Type="Unscheduled"`` (built
  only for visits that define unscheduled CRFs).
* **Common** — ``OID="CE.<model>"``, ``Type="Common"`` — the
  ``death_report_model`` and ``offstudy_model``.  An abstract / unregistered
  common model is silently skipped.

Every ``StudyEventDef`` carries an ``<Alias Context="clinicedc.schedule">``
naming the schedule it belongs to, so multi-schedule (adaptive) studies keep
their grouping even though ODM's ``Protocol`` is a flat list.

Form / item definitions
~~~~~~~~~~~~~~~~~~~~~~~~

Fields are read from the registered ``ModelAdmin``'s fieldsets, which provide
the authoritative ordering and grouping clinicians see during data entry.
Each fieldset section becomes an ``ItemGroupDef``; each field becomes an
``ItemDef`` (mapped to an ODM ``DataType`` — see :doc:`odm_mapping`).  Choice
fields produce ``CodeList`` elements.

The ``MetaDataVersion`` OID
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``MetaDataVersion/@OID`` is ``MDV.<fingerprint>``, where the fingerprint is a
SHA-256 over the canonicalized ``MetaDataVersion`` subtree.  It is therefore
**stable** across releases and changes only when the metadata itself changes.
``ClinicalDataSerializer`` computes the same fingerprint, so a data file's
``MetaDataVersionOID`` always matches the metadata edition it conforms to.
