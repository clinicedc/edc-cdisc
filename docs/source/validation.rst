Validation
==========

``edc-cdisc`` bundles the official CDISC ODM 1.3.1 XSD schema and provides
``validate_odm`` to check a document against it.

.. code-block:: python

   from edc_cdisc import validate_odm

   problems = validate_odm(xml)   # xml: bytes or an lxml element
   if problems:
       for p in problems:
           print(p)
   else:
       print("valid")

``validate_odm`` returns a **list of problem strings** — an empty list means
the document is both schema-valid and internally consistent.  It performs two
checks:

1. **XSD validation** against the bundled ODM 1.3.1 schema.  Failures are
   reported as ``"XSD line <n>: <message>"``.
2. **Reference integrity** — every OID *reference* (``StudyOID``,
   ``MetaDataVersionOID``, ``StudyEventOID``, ``FormOID``, ``ItemGroupOID``,
   ``ItemOID``, ``CodeListOID``) must point at a defined ``OID``.  A dangling
   reference is reported as ``"dangling ref: <oid>"``.

Which documents to validate
---------------------------

Reference integrity only holds *within* a self-contained document:

* **Metadata** (``MetadataSerializer``) — internal refs (``Protocol`` →
  ``StudyEventDef``, ``ItemGroupDef`` → ``ItemDef`` …) resolve → expect
  ``[]``.
* **Combined snapshot** (``SnapshotSerializer``) — the data refs resolve
  against the metadata in the same file → expect ``[]``.  This is the most
  thorough check.
* **Clinical data alone** (``ClinicalDataSerializer``) — its
  ``StudyEventOID`` / ``FormOID`` references point at definitions that live in
  the *separate* metadata file, so they will show as ``dangling ref`` here.
  That is expected; assert only that there are no ``XSD`` problems.

.. code-block:: python

   problems = validate_odm(clinical_xml)
   assert [p for p in problems if p.startswith("XSD")] == []

What XSD validation does *not* catch
------------------------------------

The ODM schema does not express OID cross-references as ``xs:keyref``, so XSD
alone will not flag a dangling reference — that is exactly why
``validate_odm`` adds the reference-integrity pass.  It also does not flag
*orphan definitions* (a def that no ref points at); the reference check is
``refs - defs``, not the reverse.

Bundled schema
--------------

The XSD files ship inside the package at ``edc_cdisc/odm_schema/`` (from the
`NCI EVS CDISC repository <https://evs.nci.nih.gov/ftp1/CDISC/schema/>`_), so
``validate_odm`` works both from a source checkout and from an installed
wheel.
