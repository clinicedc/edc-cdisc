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
to ``INSTALLED_APPS``.  It reads the existing clinicedc models
(``edc_visit_tracking.SubjectVisit``, ``edc_metadata.CrfMetadata``, etc.) at
runtime through ``django.apps.apps.get_model``.
