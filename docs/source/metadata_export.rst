Metadata Export
===============

``ODMStudySerializer`` exports the study definition as ODM XML.  This is the
structural blueprint of the study --- visit schedules, CRF forms, field
definitions, and code lists --- without any subject data.

A receiving system can use this file to understand the shape of the data before
importing clinical records.

Usage
-----

.. code-block:: python

   from edc_cdisc.odm import ODMStudySerializer

   serializer = ODMStudySerializer(
       visit_schedule=visit_schedule,
       study_oid="S.EFFECT",                  # optional, defaults to protocol name
       study_name="EFFECT Trial",             # optional, defaults to project name
       study_description="A phase III trial", # optional
       metadata_version_oid="MDV.1",          # optional
       metadata_version_name="Version 1",     # optional
   )
   xml_bytes = serializer.to_xml()


What is exported
----------------

The output follows the ODM 1.3.2 ``Study`` element hierarchy:

.. code-block:: text

   ODM
     Study
       GlobalVariables
         StudyName
         StudyDescription
         ProtocolName
       MetaDataVersion
         Protocol
           StudyEventRef ...          (one per scheduled visit)
           StudyEventRef ...          (one per unscheduled collection)
           StudyEventRef ...          (one per common event)
         StudyEventDef ...            (scheduled visits)
           FormRef ...                (each CRF in the visit, scheduled + PRN)
         StudyEventDef ...            (unscheduled, Repeating="Yes")
         StudyEventDef ...            (common events: offstudy, death report)
         FormDef ...                  (one per unique CRF model)
           ItemGroupRef ...
         ItemGroupDef ...             (fieldset sections, or one per form)
           ItemRef ...
         ItemDef ...                  (one per CRF field)
         CodeList ...                 (choice fields with CodeListItem entries)

Scheduled visits
~~~~~~~~~~~~~~~~

Each ``Visit`` in the visit schedule produces a ``StudyEventDef`` with:

* ``OID`` = ``SE.<visit_code>`` (e.g. ``SE.1000`` for baseline)
* ``Type`` = ``"Scheduled"``
* ``Repeating`` = ``"No"``
* ``FormRef`` entries for all CRFs in ``visit.crfs`` (``Mandatory="Yes"``)
  and ``visit.crfs_prn`` (``Mandatory="No"``), deduplicated.

PRN CRFs
~~~~~~~~

PRN CRFs are included in their parent visit's ``StudyEventDef`` with
``Mandatory="No"``.  If a PRN CRF also appears in the scheduled collection for
that visit, only the scheduled (``Mandatory="Yes"``) entry is kept.

Unscheduled visits
~~~~~~~~~~~~~~~~~~

Unscheduled CRF collections (``visit.crfs_unscheduled``) are exported as
separate ``StudyEventDef`` elements with:

* ``Type`` = ``"Unscheduled"``
* ``Repeating`` = ``"Yes"``

Collections are deduplicated by their CRF content, so identical unscheduled
collections across visits produce a single definition.

Common events
~~~~~~~~~~~~~

Models referenced by ``visit_schedule.death_report_model`` and
``visit_schedule.offstudy_model`` are exported as ``StudyEventDef`` elements
with ``Type="Common"``.  Abstract-only models (e.g.
``edc_adverse_event.deathreport``) are silently skipped.

Field definitions
~~~~~~~~~~~~~~~~~

For each CRF model, fields are read from the registered ``ModelAdmin``'s
``fieldsets`` if available.  This provides the authoritative field ordering and
grouping that clinicians see in the data-entry interface.

Fields are mapped from Django field types to ODM data types (see
:doc:`odm_mapping`).  Choice fields produce ``CodeList`` elements with
``CodeListItem`` entries.

The following are excluded:

* ``subject_visit`` / ``related_visit`` foreign keys
* Audit fieldset sections (``"Audit"``, ``"Action"``)
