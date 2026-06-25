edc-cdisc
=========

CDISC ODM export for the `clinicedc <https://github.com/clinicedc>`_
clinical-trial data-collection framework.

``edc-cdisc`` reads the visit schedule, CRF definitions, and submitted data
from a clinicedc installation and produces standards-compliant XML in
`CDISC ODM 1.3.1 <https://www.cdisc.org/standards/data-exchange/odm>`_
format.

It provides three serializers, all built on the same class hierarchy
(``Serializer`` → ``VisitScheduleSerializer`` → the concrete serializers):

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Serializer
     - Produces
   * - ``MetadataSerializer``
     - ``<Study>`` — the study definition (visit schedule, forms, items,
       code lists)
   * - ``ClinicalDataSerializer``
     - ``<ClinicalData>`` — submitted CRF values
   * - ``SnapshotSerializer``
     - a combined ``<Study>`` + ``<ClinicalData>`` document

Transactional (incremental) export is planned but not yet implemented; it
will be driven by the audit trail.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quickstart
   metadata_export
   data_export_snapshot
   data_export_combined
   validation
   odm_mapping
   sdtm_design
   api
