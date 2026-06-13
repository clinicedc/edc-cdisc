Validation
==========

``edc-cdisc`` bundles the official CDISC ODM 1.3.1 XSD schema and provides a
management command to validate exports against it.


Management command
------------------

.. code-block:: bash

   python manage.py validate_odm_export

This runs all four serializers (Metadata Export, Snapshot Data Export, Combined
Snapshot, Transactional Data Export) against every registered visit schedule,
validates each output against the XSD, and reports statistics.

Options
~~~~~~~

.. code-block:: text

   --visit-schedule NAME   Validate a single visit schedule (default: all)
   --since-days N          Transactional export lookback in days (default: 30)
   --output-dir PATH       Write XML files to this directory for inspection
   --skip-xsd              Skip XSD validation (just export and report stats)

Examples
~~~~~~~~

Validate all visit schedules and write XML files for inspection:

.. code-block:: bash

   python manage.py validate_odm_export --output-dir /tmp/odm_export

Validate a specific visit schedule with a 7-day transactional window:

.. code-block:: bash

   python manage.py validate_odm_export --visit-schedule my_schedule --since-days 7

Export only (skip schema validation):

.. code-block:: bash

   python manage.py validate_odm_export --output-dir /tmp/odm_export --skip-xsd


Sample output
~~~~~~~~~~~~~

.. code-block:: text

   Loading XSD schema from .../ODM1-3-1.xsd ... OK

   ============================================================
    Visit Schedule: my_visit_schedule
   ============================================================

     Metadata Export
     ---------------
       XML size: 45,230 bytes
       FileType: Snapshot
       Study elements: 1
       StudyEventDefs: 12
       FormDefs: 28
       ItemGroupDefs: 42
       ItemDefs: 310
       CodeLists: 85
       XSD validation: PASSED

     Snapshot Data Export
     --------------------
       XML size: 1,234,567 bytes
       FileType: Snapshot
       ClinicalData elements: 1
       Subjects: 150
       StudyEvents: 1,420
       Forms: 3,850
       ItemData values: 48,200
       XSD validation: PASSED

     ...

   ============================================================
    Summary
   ============================================================
     Passed: 4
     Failed: 0

     ALL PASSED


XSD schema
----------

The bundled XSD schema files are from the
`NCI EVS CDISC repository <https://evs.nci.nih.gov/ftp1/CDISC/schema/>`_.
The ODM 1.3.1 schema validates all output produced by ``edc-cdisc``.

Schema files are located in ``edc_cdisc/odm/schema/``:

* ``cdisc-odm-1.3.1/ODM1-3-1.xsd`` --- wrapper schema
* ``cdisc-odm-1.3.1/ODM1-3-1-foundation.xsd`` --- foundation definitions
* ``core/xml.xsd`` --- XML namespace schema
* ``core/xmldsig-core-schema.xsd`` --- XML digital signature schema
