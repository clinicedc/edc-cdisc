ODM Mapping Reference
=====================

This page documents how clinicedc constructs are mapped to CDISC ODM 1.3.1
elements and attributes.

OID conventions
---------------

All OIDs follow a prefix-dot-key pattern:

.. list-table::
   :header-rows: 1
   :widths: 10 35 55

   * - Prefix
     - Example
     - Source
   * - ``S.``
     - ``S.EFFECT``
     - Protocol name
   * - ``SE.``
     - ``SE.1000``
     - ``visit.visit_code``
   * - ``F.``
     - ``F.effect_subject.bloodresults``
     - ``app_label.model_name``
   * - ``IG.``
     - ``IG.effect_subject.bloodresults``
     - Model label (no fieldsets) or fieldset section key
   * - ``I.``
     - ``I.effect_subject.bloodresults.hb``
     - ``app_label.model_name.field_name``
   * - ``CL.``
     - ``CL.effect_subject.bloodresults.hb_units``
     - Model label + field name

Django field type mapping
-------------------------

Django model field types are mapped to ODM ``DataType`` values:

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
``NullBooleanField``             ``boolean``
``DateField``                    ``date``
``DateTimeField``                ``datetime``
``TimeField``                    ``time``
``UUIDField``                    ``text``
``FileField``                    ``URI``
``FilePathField``                ``URI``
``EmailField``                   ``text``
``URLField``                     ``URI``
``IPAddressField``               ``text``
``GenericIPAddressField``        ``text``
``BinaryField``                  ``hexBinary``
``DurationField``                ``text``
``JSONField``                    ``text``
===============================  ==============

Fieldset mapping
----------------

When a ``ModelAdmin`` with ``fieldsets`` is registered for a CRF model, the
fieldset structure is used to create ``ItemGroupDef`` / ``ItemGroupData``
sections:

* Each fieldset tuple ``(name, {"fields": [...]})`` becomes one
  ``ItemGroupDef``.
* The ``ItemGroupOID`` is derived from the model label, fieldset name, and
  positional order to ensure uniqueness.
* Fieldsets named ``"Audit"`` or ``"Action"`` are excluded (these contain
  system columns, not clinical data).

If no ``ModelAdmin`` fieldsets are found, a single ``ItemGroupDef`` is created
containing all non-excluded fields from ``Model._meta.get_fields()``.

Excluded fields
---------------

The following fields are always excluded from ODM output:

* ``subject_visit`` --- the foreign key to ``SubjectVisit`` (structural, not
  clinical data)
* ``related_visit`` --- the related-visit foreign key
* All ``ForeignKey`` and ``OneToOneField`` relations (structural references)
* All fields in the ``AuditModelMixin`` (``created``, ``modified``,
  ``user_created``, ``user_modified``, ``hostname_*``, ``device_*``,
  ``locale_*``) --- these are system columns

Code lists
----------

Fields with ``choices`` defined produce ``CodeList`` elements:

.. code-block:: xml

   <CodeList OID="CL.myapp.mymodel.status" Name="status" DataType="text">
     <CodeListItem CodedValue="alive">
       <Decode><TranslatedText>Alive</TranslatedText></Decode>
     </CodeListItem>
     <CodeListItem CodedValue="dead">
       <Decode><TranslatedText>Dead</TranslatedText></Decode>
     </CodeListItem>
   </CodeList>

The corresponding ``ItemDef`` references the code list via a ``CodeListRef``
child element.

StudyEventDef types
-------------------

.. list-table::
   :header-rows: 1
   :widths: 20 20 15 45

   * - Source
     - ODM Type
     - Repeating
     - Notes
   * - Scheduled visit
     - ``Scheduled``
     - ``No``
     - One per ``Visit`` in schedule
   * - PRN CRFs
     - *(within parent scheduled event)*
     - n/a
     - ``Mandatory="No"`` on ``FormRef``
   * - Unscheduled collections
     - ``Unscheduled``
     - ``Yes``
     - Deduplicated by CRF content
   * - Death report
     - ``Common``
     - ``No``
     - From ``visit_schedule.death_report_model``
   * - Offstudy
     - ``Common``
     - ``No``
     - From ``visit_schedule.offstudy_model``
