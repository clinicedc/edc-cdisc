Installation
============

Requirements
------------

* Python >= 3.12
* Django >= 5.2
* clinicedc >= 4.0.6
* lxml >= 5.0

Install
-------

Install with pip (or uv):

.. code-block:: bash

   pip install edc-cdisc

Or add to your ``pyproject.toml``:

.. code-block:: toml

   [project]
   dependencies = [
       "edc-cdisc",
   ]

``edc-cdisc`` does not define any Django models and does not need to be added
to ``INSTALLED_APPS``.  It reads the existing clinicedc constructs — the
registered ``VisitSchedule``, the CRF ``ModelAdmin`` fieldsets, and the
``SubjectVisit`` / CRF instances — at runtime.

.. note::

   Every CRF model in the visit schedule must have a registered
   ``ModelAdmin`` whose fieldsets reference only real model fields.  The
   serializers read those fieldsets to build the form/item definitions and
   will raise if an admin is missing or a fieldset lists a non-field.
