Quickstart
==========

``edc-cdisc`` provides four serializers, each producing a different flavour of
CDISC ODM 1.3.1 XML:

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Serializer
     - FileType
     - Purpose
   * - ``ODMStudySerializer``
     - Snapshot
     - Study metadata (visit schedule, CRF definitions, item definitions,
       code lists)
   * - ``ODMClinicalDataSerializer``
     - Snapshot
     - Full data dump of submitted CRF values
   * - ``ODMSnapshotSerializer``
     - Snapshot
     - Combined: study metadata **and** clinical data in one file
   * - ``ODMTransactionalSerializer``
     - Transactional
     - Incremental export of CRF data changed since a given timestamp

All four follow the same pattern:

1. Instantiate with a ``VisitSchedule`` (and any optional parameters).
2. Call ``.to_xml()`` for UTF-8 bytes or ``.to_etree()`` for an lxml Element.

Minimal example
---------------

.. code-block:: python

   from edc_visit_schedule.site_visit_schedules import site_visit_schedules

   from edc_cdisc.odm import (
       ODMClinicalDataSerializer,
       ODMSnapshotSerializer,
       ODMStudySerializer,
       ODMTransactionalSerializer,
   )

   # Get the registered visit schedule
   visit_schedule = site_visit_schedules.get_visit_schedule("my_visit_schedule")

   # 1. Export study metadata only
   metadata_xml = ODMStudySerializer(
       visit_schedule=visit_schedule,
   ).to_xml()

   # 2. Export all submitted data only (snapshot)
   data_xml = ODMClinicalDataSerializer(
       visit_schedule=visit_schedule,
   ).to_xml()

   # 3. Export metadata + data in a single file (combined snapshot)
   combined_xml = ODMSnapshotSerializer(
       visit_schedule=visit_schedule,
   ).to_xml()

   # 4. Export only data changed in the last 24 hours
   from datetime import UTC, datetime, timedelta

   since = datetime.now(tz=UTC) - timedelta(hours=24)
   delta_xml = ODMTransactionalSerializer(
       visit_schedule=visit_schedule,
       since=since,
   ).to_xml()

Writing to a file
-----------------

.. code-block:: python

   from pathlib import Path

   path = Path("/tmp/study_metadata.xml")
   path.write_bytes(
       ODMStudySerializer(visit_schedule=visit_schedule).to_xml()
   )

Filtering by subject
--------------------

``ODMClinicalDataSerializer``, ``ODMSnapshotSerializer``, and
``ODMTransactionalSerializer`` accept an optional ``subject_identifiers``
parameter to restrict output to specific subjects:

.. code-block:: python

   xml = ODMClinicalDataSerializer(
       visit_schedule=visit_schedule,
       subject_identifiers=["100-0001", "100-0002"],
   ).to_xml()
