Pandas Integration
==================

``edc-cdisc`` can convert ODM XML exports into pandas DataFrames for analysis,
reporting, and further transformation.

.. note::

   pandas is an optional dependency.  Install it separately if not already
   available: ``pip install pandas``.


Clinical data
-------------

``odm_to_dataframe()`` extracts ``ClinicalData`` from any ODM XML source
(bytes, file path, or serializer output) into a DataFrame.

Wide format (default)
~~~~~~~~~~~~~~~~~~~~~

One row per subject/event/form combination, one column per ``ItemOID``:

.. code-block:: python

   from edc_cdisc.odm import ODMSnapshotSerializer, odm_to_dataframe

   xml = ODMSnapshotSerializer(visit_schedule=visit_schedule).to_xml()
   df = odm_to_dataframe(xml)

   #   subject       event              form                                    I.myapp.mymodel.hb  ...
   # 0 100-0001      SE.1000            F.myapp.mymodel                         12.5                ...

Long format
~~~~~~~~~~~

One row per ``ItemData`` value --- useful for filtering, grouping, and joining:

.. code-block:: python

   df = odm_to_dataframe(xml, long=True)

   #   subject   event    form               item_group              item                        value
   # 0 100-0001  SE.1000  F.myapp.mymodel    IG.myapp.mymodel        I.myapp.mymodel.hb          12.5
   # 1 100-0001  SE.1000  F.myapp.mymodel    IG.myapp.mymodel        I.myapp.mymodel.hb_units    g/dL

Transactional data includes a ``transaction_type`` column (``Insert`` or
``Update``):

.. code-block:: python

   from edc_cdisc.odm import ODMTransactionalSerializer, odm_to_dataframe

   xml = ODMTransactionalSerializer(
       visit_schedule=visit_schedule, since=since
   ).to_xml()
   df = odm_to_dataframe(xml, long=True)
   inserts = df[df["transaction_type"] == "Insert"]


Reading from files
~~~~~~~~~~~~~~~~~~

Pass a file path instead of bytes --- works with files written by
``validate_odm_export --output-dir``:

.. code-block:: python

   df = odm_to_dataframe("/tmp/odm_export/my_schedule_snapshot_data_export.xml")


Study metadata
--------------

``odm_metadata_to_dataframe()`` extracts ``Study`` metadata into a dictionary
of DataFrames:

.. code-block:: python

   from edc_cdisc.odm import ODMStudySerializer, odm_metadata_to_dataframe

   xml = ODMStudySerializer(visit_schedule=visit_schedule).to_xml()
   meta = odm_metadata_to_dataframe(xml)

   meta["study_events"]   # StudyEventDef: OID, Name, Repeating, Type
   meta["forms"]          # FormDef: OID, Name, Repeating
   meta["item_groups"]    # ItemGroupDef: OID, Name, Repeating
   meta["items"]          # ItemDef: OID, Name, DataType, CodeListOID (if applicable)
   meta["code_lists"]     # CodeListItem: CodeListOID, CodeListName, CodedValue, Decode

This also works with combined snapshot XML (``ODMSnapshotSerializer``), which
contains both ``Study`` and ``ClinicalData`` elements:

.. code-block:: python

   from edc_cdisc.odm import ODMSnapshotSerializer, odm_to_dataframe, odm_metadata_to_dataframe

   xml = ODMSnapshotSerializer(visit_schedule=visit_schedule).to_xml()
   df = odm_to_dataframe(xml)
   meta = odm_metadata_to_dataframe(xml)
