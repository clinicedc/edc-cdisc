Data Export --- Transactional
=============================

``ODMTransactionalSerializer`` exports only CRF data that has changed since a
given timestamp.  The output uses ``FileType="Transactional"`` and each
``FormData`` element carries a ``TransactionType`` attribute.

This is the incremental counterpart to the snapshot export and is intended for
periodic synchronization workflows --- e.g. nightly feeds to a data warehouse
or regulatory submission pipeline.

Usage
-----

.. code-block:: python

   from datetime import UTC, datetime, timedelta

   from edc_cdisc.odm import ODMTransactionalSerializer

   since = datetime.now(tz=UTC) - timedelta(hours=24)
   serializer = ODMTransactionalSerializer(
       visit_schedule=visit_schedule,
       since=since,
       subject_identifiers=None,      # optional
       study_oid="S.EFFECT",          # optional
       metadata_version_oid="MDV.1",  # optional
   )
   xml_bytes = serializer.to_xml()

Transaction types
-----------------

The ``TransactionType`` is determined by comparing the CRF instance's audit
timestamps against the ``since`` cutoff:

==================  =============================================
TransactionType     Condition
==================  =============================================
``Insert``          ``instance.created >= since``
``Update``          ``instance.modified >= since`` **and**
                    ``instance.created < since``
*(omitted)*         Both ``created`` and ``modified`` are before
                    ``since`` --- the CRF has not changed
==================  =============================================

Every clinicedc model inherits ``created`` and ``modified`` ``DateTimeField``
columns from ``django_audit_fields.AuditModelMixin``, so this classification
is available for all CRFs without additional instrumentation.

Output structure
----------------

The XML structure is identical to the snapshot export, except:

* The root ``ODM`` element has ``FileType="Transactional"``.
* Each ``FormData`` element has a ``TransactionType`` attribute.
* Subjects and visits with no changed CRFs are omitted entirely.

.. code-block:: text

   ODM (FileType="Transactional")
     ClinicalData
       SubjectData (SubjectKey=subject_identifier)
         StudyEventData (StudyEventOID="SE.<visit_code>")
           FormData (FormOID="F.<model>", TransactionType="Insert")
             ItemGroupData ...
               ItemData ...
           FormData (FormOID="F.<model>", TransactionType="Update")
             ...

Typical workflow
----------------

A common pattern is to record the timestamp of each successful export and use
it as ``since`` for the next run:

.. code-block:: python

   from datetime import UTC, datetime
   from pathlib import Path

   # Load last export time (or epoch for first run)
   marker = Path("/var/run/edc_cdisc_last_export")
   if marker.exists():
       since = datetime.fromisoformat(marker.read_text().strip())
   else:
       since = datetime(2000, 1, 1, tzinfo=UTC)

   now = datetime.now(tz=UTC)
   xml = ODMTransactionalSerializer(
       visit_schedule=visit_schedule,
       since=since,
   ).to_xml()

   # Write the export
   Path(f"/exports/delta_{now:%Y%m%d%H%M%S}.xml").write_bytes(xml)

   # Update the marker
   marker.write_text(now.isoformat())

Limitations
-----------

* **Deletes are not tracked.**  If a CRF instance is deleted (or its metadata
  entry status reverts from ``KEYED``), no ``TransactionType="Remove"`` element
  is emitted.  clinicedc does not hard-delete CRF records in normal operation,
  so this is rarely an issue in practice.

* **Granularity is per-form.**  A single field change causes the entire
  ``FormData`` (all fields) to be included in the output.  Per-field change
  tracking would require a different audit mechanism.
