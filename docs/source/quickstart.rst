Quickstart
==========

All three serializers follow the same pattern:

1. Instantiate with ``edc_module_name`` and a registered ``VisitSchedule``
   (plus any optional parameters).
2. Call ``.to_xml()`` for UTF-8 bytes, or ``.to_etree()`` for an lxml element.

``edc_module_name`` is the EDC project package (e.g. ``"meta_edc"``); it is
used for the ODM ``SourceSystem`` / ``SourceSystemVersion`` header attributes.

Minimal example
---------------

.. code-block:: python

   from edc_visit_schedule.site_visit_schedules import site_visit_schedules

   from edc_cdisc.serializers import (
       MetadataSerializer,
       ClinicalDataSerializer,
       SnapshotSerializer,
   )

   visit_schedule = site_visit_schedules.visit_schedules.get("visit_schedule")

   # 1. study metadata only
   metadata_xml = MetadataSerializer(
       edc_module_name="meta_edc",
       visit_schedule=visit_schedule,
   ).to_xml()

   # 2. submitted data only
   data_xml = ClinicalDataSerializer(
       edc_module_name="meta_edc",
       visit_schedule=visit_schedule,
   ).to_xml()

   # 3. combined metadata + data in one document
   snapshot_xml = SnapshotSerializer(
       edc_module_name="meta_edc",
       visit_schedule=visit_schedule,
   ).to_xml()

Writing to a file
-----------------

.. code-block:: python

   from pathlib import Path

   Path("/tmp/odm_snapshot.xml").write_bytes(
       SnapshotSerializer(
           edc_module_name="meta_edc", visit_schedule=visit_schedule
       ).to_xml()
   )

Validating the output
---------------------

``validate_odm`` checks the document against the bundled ODM 1.3.1 XSD *and*
verifies that every OID reference resolves.  An empty list means it is valid
and internally consistent:

.. code-block:: python

   from edc_cdisc import validate_odm

   problems = validate_odm(snapshot_xml)
   assert problems == []

See :doc:`validation` for details.

Common options
--------------

``ClinicalDataSerializer`` and ``SnapshotSerializer`` accept:

* ``subject_identifiers`` — restrict the export to specific subjects
  (``None`` = all).
* ``include_nulls`` — when ``True``, emit ``<ItemData IsNull="Yes"/>`` for
  null fields instead of omitting them, so every form instance carries a
  fixed number of items (useful for reconciliation).

.. code-block:: python

   ClinicalDataSerializer(
       edc_module_name="meta_edc",
       visit_schedule=visit_schedule,
       subject_identifiers=["100-0001", "100-0002"],
       include_nulls=True,
   ).to_xml()
