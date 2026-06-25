SDTM Export — Design Notes
==========================

Status: **design / exploration** (no code yet).  Target: **SDTMIG 3.4**,
primary output **Dataset-JSON v1.1**.

This document scopes a future SDTM (Study Data Tabulation Model) export
alongside the existing ODM 1.3.1 export.  SDTM is one of the foundational
standards required for data submission to the FDA (and PMDA).

Why SDTM is a different kind of problem from ODM
------------------------------------------------

The ODM exporter is **mechanical and lossless**: it walks the clinicedc
structure (``RegisteredSubject`` → related visit → CRF → fields) and emits a
faithful hierarchical XML mirror.  OIDs are derived from model labels and
field names; no clinical interpretation is needed, which is why it is generic
across any clinicedc trial.

SDTM is the opposite.  It is a **fixed target model**, not a dump of the
source.  Data must be reshaped and re-coded into a standard set of flat
domain tables.

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Aspect
     - ODM (today)
     - SDTM (proposed)
   * - Shape
     - Hierarchical XML mirror of the EDC
     - One flat table per **domain** (DM, AE, VS, LB, EX, CM, MH, …)
   * - Direction
     - Source-faithful
     - Conform-to-standard
   * - Variable names
     - Your field names (OIDs)
     - Fixed CDISC names (``USUBJID``, ``--TESTCD``, ``--ORRES``,
       ``VISITNUM``, …)
   * - Coding
     - As entered
     - CDISC Controlled Terminology + MedDRA / WHODrug
   * - Mapping
     - Automatic
     - **Requires per-CRF SME mapping**
   * - Output
     - ODM XML
     - ``.xpt`` (SAS v5) and/or **Dataset-JSON**, plus **define.xml**

The honest headline: SDTM **cannot** be fully auto-generated from arbitrary
clinicedc data the way ODM can.  A *Findings* domain such as VS or LB is
**vertical** — one row per measurement (``VSTESTCD=SYSBP``, ``VSORRES=120``,
``VSORRESU=mmHg``) — whereas a CRF stores those as horizontal columns.  That
transpose, plus the controlled-terminology decisions, is inherently a
study-specific, human-in-the-loop mapping exercise.

SDTM observation classes
------------------------

Every domain belongs to one general observation class.  Identify the class
first; the domain follows.

* **Interventions** — CM (concomitant meds), EX (exposure), EC, SU, PR
* **Events** — AE (adverse events), MH (medical history), DS (disposition),
  CE
* **Findings** — VS (vital signs), LB (labs), EG (ECG), QS (questionnaires),
  FA (findings about)
* **Special Purpose** — DM (demographics), CO, SE (subject elements),
  SV (subject visits)
* **Trial Design** — TS, TA, TE, TV, TI, TD, TM

What clinicedc can supply (mostly) for free
--------------------------------------------

clinicedc already holds the structured metadata SDTM needs for a meaningful
slice:

* **Trial Design domains** (``TS, TA, TE, TV, TI, SV, SE``) — the
  ``visit_schedule`` + ``edc_protocol`` config already encode visits, epochs,
  arms, and timing.  These map almost directly and are the most "free" win.
* **DM (Demographics)** — assembled from ``RegisteredSubject`` + consent +
  screening + a demographics CRF.  Mostly derivable with a thin mapping.
* **SV / SE (Subject Visits / Elements)** — straight from the related-visit
  model already iterated in :file:`clinical_data_serializer.py`.

Everything else (AE, CM, MH, VS, LB, EG, EX, …) needs a **mapping-spec
layer**: a declarative config saying "CRF model ``X`` field ``Y`` → domain VS,
variable ``VSORRES``, ``VSTESTCD=SYSBP``, unit mmHg".

What existing code is directly reusable
---------------------------------------

#. **define.xml is ODM.**  Define-XML 2.0/2.1 is a CDISC extension of the same
   ODM schema already emitted (``MetaDataVersion``, ``ItemGroupDef``,
   ``ItemDef``, ``CodeList``).  ``MetadataSerializer`` is the natural
   foundation for the define.xml that must accompany every SDTM submission.
#. **PII guards** (encrypted-field skip, consent whitelist) carry over
   unchanged and remain mandatory — SDTM datasets must never leak
   ``django_crypto_fields`` data.
#. The subject/visit traversal in :file:`clinical_data_serializer.py` is the
   same traversal a domain builder needs.

Output format: Dataset-JSON
---------------------------

Target **Dataset-JSON v1.1** (released 2024-12-05) first:

* No SAS dependency; trivially generated from a pandas ``DataFrame``
  (records = rows, columns carry name/label/type metadata).
* Can optionally reference a Define-XML document for full metadata.

``.xpt`` (SAS Transport v5) is the definitively FDA-required format and can be
added later as an additional serialization target (e.g. via ``pyreadstat``),
subject to its 8-char name / value-length constraints.

Proposed phased plan
--------------------

#. **Phase 1 — Trial Design + DM, Dataset-JSON.**  Auto-derive
   ``TS/TA/TE/TV/TI/SV/SE`` and ``DM`` from the visit schedule +
   registration/consent.  Emit Dataset-JSON.  Proves the pipeline end-to-end
   with zero SME mapping.
#. **Phase 2 — Mapping-spec layer + 1–2 domains** (e.g. VS and AE) to
   validate the transpose + controlled-terminology approach.
#. **Phase 3 — define.xml** reusing ``MetadataSerializer``, plus **CORE**
   validation (CDISC's open-source conformance engine) wired into a
   management command, analogous to ``validate_odm_export``.

Open questions
--------------

* Controlled Terminology source / version pinning (CDISC CT packages;
  MedDRA & WHODrug licensing for AE/CM).
* How mapping specs are declared and stored (per-trial Python config vs.
  data-driven).
* Whether ``--SEQ`` and ``RELREC`` relationships are needed in early phases.
* SUPPQUAL handling for non-standard CRF variables.
