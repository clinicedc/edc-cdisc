Combined Snapshot Export
========================

``ODMSnapshotSerializer`` produces a single ODM file containing both the study
metadata (``<Study>``) and all submitted clinical data (``<ClinicalData>``).
This is the format most commonly expected by receiving systems that need a
self-describing data package.

Usage
-----

.. code-block:: python

   from edc_cdisc.odm import ODMSnapshotSerializer

   serializer = ODMSnapshotSerializer(
       visit_schedule=visit_schedule,
       study_oid="S.EFFECT",                  # optional
       study_name="EFFECT Trial",             # optional
       study_description="A phase III trial", # optional
       metadata_version_oid="MDV.1",          # optional
       metadata_version_name="Version 1",     # optional
       subject_identifiers=["100-0001"],       # optional filter
   )
   xml_bytes = serializer.to_xml()


What is exported
----------------

The output follows this ODM element hierarchy:

.. code-block:: text

   ODM (FileType="Snapshot")
     Study                     (study metadata)
       GlobalVariables
       MetaDataVersion
         Protocol
         StudyEventDef ...
         FormDef ...
         ItemGroupDef ...
         ItemDef ...
         CodeList ...
     ClinicalData              (submitted CRF values)
       SubjectData ...
         StudyEventData ...
           FormData ...
             ItemGroupData ...
               ItemData ...

The ``Study`` element is identical to what ``ODMStudySerializer`` produces.
The ``ClinicalData`` element is identical to what ``ODMClinicalDataSerializer``
produces.  Both share the same ``StudyOID`` and ``MetaDataVersionOID`` so the
receiving system can link data to definitions.


When to use this vs. separate serializers
-----------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Use ``ODMSnapshotSerializer``
     - Use separate serializers
   * - Self-contained export file that a receiver can process without prior
       knowledge of the study structure
     - Metadata and data are exchanged independently (e.g. metadata sent once,
       data sent repeatedly)
   * - Regulatory submissions or archival
     - Incremental data feeds (use ``ODMTransactionalSerializer`` instead)
