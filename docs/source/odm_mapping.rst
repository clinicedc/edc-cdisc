ODM Mapping Reference
=====================

How clinicedc constructs map to CDISC ODM 1.3.1 elements and attributes.

OID conventions
---------------

All OIDs follow a prefix-dot-key pattern.

.. list-table::
   :header-rows: 1
   :widths: 10 38 52

   * - Prefix
     - Example
     - Source
   * - ``S.``
     - ``S.META``
     - Protocol name (``Study`` / ``ClinicalData``)
   * - ``MDV.``
     - ``MDV.9f1c2a4b6d8e``
     - SHA-256 fingerprint of the ``MetaDataVersion`` content
   * - ``SE.``
     - ``SE.1000``
     - ``visit.code`` — **scheduled** study event
   * - ``UE.``
     - ``UE.1000``
     - ``visit.code`` — **unscheduled** study event
   * - ``CE.``
     - ``CE.meta_ae.deathreport``
     - common (death / offstudy) model label
   * - ``F.``
     - ``F.meta_subject.bloodresults``
     - ``app_label.model_name``
   * - ``IG.``
     - ``IG.meta_subject.bloodresults.haematology.1``
     - ``app_label.model_name`` + fieldset section slug + order
   * - ``I.``
     - ``I.meta_subject.bloodresults.hb``
     - ``app_label.model_name.field_name``
   * - ``CL.``
     - ``CL.meta_subject.bloodresults.hb_units``
     - ``app_label.model_name.field_name``

Study events
------------

.. list-table::
   :header-rows: 1
   :widths: 22 14 12 52

   * - Source
     - ODM Type
     - Repeating
     - Notes
   * - Scheduled visit
     - ``Scheduled``
     - ``No``
     - ``SE.<code>``; ``FormRef``\s = ``crfs`` + missed CRF + remaining PRNs
   * - Unscheduled visit
     - ``Unscheduled``
     - ``Yes``
     - ``UE.<code>``; built per visit that defines ``crfs_unscheduled``
   * - Death report / offstudy
     - ``Common``
     - ``No``
     - ``CE.<model>``; abstract / unregistered models are skipped

Every ``StudyEventDef`` carries an ``<Alias Context="clinicedc.schedule"
Name="…"/>`` identifying the schedule it belongs to.  In the data,
``StudyEventData`` maps a ``SubjectVisit`` to ``SE.<code>`` when
``visit_code_sequence == 0`` and to ``UE.<code>`` with a
``StudyEventRepeatKey`` when it is ``> 0``.

Fieldset mapping
----------------

Each CRF model **must** have a registered ``ModelAdmin``.  Its ``fieldsets``
provide the field ordering and grouping:

* Each fieldset ``(name, {"fields": [...]})`` becomes one ``ItemGroupDef``.
* The ``ItemGroupOID`` includes the fieldset's positional order, so two
  sections that slugify to the same name still get unique OIDs.
* Fieldsets named ``"Audit"`` or ``"Action"`` are excluded.

The data side (``FormData`` → ``ItemGroupData`` → ``ItemData``) walks the
**same** fieldsets, so every ``ItemData`` OID resolves to an ``ItemDef``.

Excluded fields
---------------

These are dropped from both the metadata and the data:

* ``subject_visit`` and ``related_visit`` — structural foreign keys.
* ``consent_model`` — consent provenance, not a CRF answer.
* The ``AuditModelMixin`` system columns — ``user_created``,
  ``user_modified``, ``hostname_*``, ``device_*``, ``locale_*`` — **except**
  ``created`` and ``modified``, which are retained.

.. note::

   Other ``ForeignKey`` / ``OneToOneField`` fields are currently emitted as
   text (the stored UUID), using ``field.name`` for the OID and
   ``field.attname`` for the value.  This is a temporary measure; proper
   relation handling (FK → coded value, M2M → repeating items, list models)
   is planned.

Django field type mapping
-------------------------

Django model field types map to ODM ``DataType`` values:

===============================  ==============
Django field                     ODM DataType
===============================  ==============
``CharField``                    ``text``
``TextField``                    ``text``
``SlugField``                    ``text``
``IntegerField``                 ``integer``
``SmallIntegerField``            ``integer``
``BigIntegerField``              ``integer``
``PositiveIntegerField``         ``integer``
``PositiveSmallIntegerField``    ``integer``
``PositiveBigIntegerField``      ``integer``
``AutoField``                    ``integer``
``BigAutoField``                 ``integer``
``FloatField``                   ``float``
``DecimalField``                 ``float``
``BooleanField``                 ``boolean``
``DateField``                    ``date``
``DateTimeField``                ``datetime``
``TimeField``                    ``time``
``UUIDField``                    ``text``
``FileField``                    ``URI``
``FilePathField``                ``URI``
``EmailField``                   ``text``
``URLField``                     ``URI``
``BinaryField``                  ``hexBinary``
``DurationField``                ``text``
``JSONField``                    ``text``
===============================  ==============

Anything not listed defaults to ``text``.

Code lists
----------

Fields with ``choices`` produce ``CodeList`` elements, and the corresponding
``ItemDef`` references them via a ``CodeListRef``:

.. code-block:: xml

   <CodeList OID="CL.myapp.mymodel.status" Name="status choices" DataType="text">
     <CodeListItem CodedValue="alive">
       <Decode><TranslatedText xml:lang="en">Alive</TranslatedText></Decode>
     </CodeListItem>
     <CodeListItem CodedValue="dead">
       <Decode><TranslatedText xml:lang="en">Dead</TranslatedText></Decode>
     </CodeListItem>
   </CodeList>
