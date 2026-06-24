Combined Snapshot Export
========================

``SnapshotSerializer`` produces a single ODM document containing both the
study metadata (``<Study>``) and the submitted data (``<ClinicalData>``).
This is the format most commonly expected by a receiving system, and the
right shape for an external auditor — it is self-describing and self-validating.

Usage
-----

.. code-block:: python

   from edc_cdisc.serializers import SnapshotSerializer

   xml_bytes = SnapshotSerializer(
       edc_module_name="meta_edc",
       visit_schedule=visit_schedule,
       subject_identifiers=["100-0001"],   # optional
       include_nulls=True,                 # optional
   ).to_xml()

Output structure
----------------

.. code-block:: text

   ODM
     Study
       GlobalVariables
       MetaDataVersion  (OID="MDV.<fp>")
       ...
     ClinicalData  (StudyOID="S.<protocol>" MetaDataVersionOID="MDV.<fp>")
       SubjectData ...

Internally it composes a ``MetadataSerializer`` and a
``ClinicalDataSerializer`` with the same arguments and appends both results
under one ``<ODM>`` root.  Because the ``MetaDataVersion`` fingerprint is
deterministic, the ``ClinicalData/@MetaDataVersionOID`` always equals the
``MetaDataVersion/@OID`` in the same file.

Validation
----------

A combined snapshot is the right document for the full integrity check,
because the data's OID references resolve against the metadata definitions in
the *same* file:

.. code-block:: python

   from edc_cdisc import validate_odm

   assert validate_odm(xml_bytes) == []   # XSD-valid AND every ref resolves

See :doc:`validation`.
