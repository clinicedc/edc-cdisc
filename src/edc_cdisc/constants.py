from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from django.db import models
from django_audit_fields.constants import AUDIT_MODEL_FIELDS

if TYPE_CHECKING:
    from collections.abc import Callable

ODM_NAMESPACE = "http://www.cdisc.org/ns/odm/v1.3"

SERIALIZE_MAP: tuple[tuple[type, Callable], ...] = (
    (bool, lambda v: "true" if v else "false"),
    (datetime, lambda v: v.isoformat()),
    (date, lambda v: v.isoformat()),
    (time, lambda v: v.isoformat()),
    (Decimal, str),
    (float, str),
    (int, str),
    (UUID, str),
)

NSMAP = {None: ODM_NAMESPACE}

ODM_VERSION = "1.3.1"
# ODM_METADATA_VERSION_OID = "MDV.1"
# ODM_METADATA_VERSION_NAME = "Version {}"

DJANGO_TO_ODM_DATATYPE: dict[type[models.Field], str] = {
    models.CharField: "text",
    models.TextField: "text",
    models.SlugField: "text",
    models.IntegerField: "integer",
    models.SmallIntegerField: "integer",
    models.BigIntegerField: "integer",
    models.PositiveIntegerField: "integer",
    models.PositiveSmallIntegerField: "integer",
    models.PositiveBigIntegerField: "integer",
    models.AutoField: "integer",
    models.BigAutoField: "integer",
    models.FloatField: "float",
    models.DecimalField: "float",
    models.BooleanField: "boolean",
    models.NullBooleanField: "boolean",
    models.DateField: "date",
    models.DateTimeField: "datetime",
    models.TimeField: "time",
    models.UUIDField: "text",
    models.FileField: "URI",
    models.FilePathField: "URI",
    models.EmailField: "text",
    models.URLField: "URI",
    models.IPAddressField: "text",
    models.GenericIPAddressField: "text",
    models.BinaryField: "hexBinary",
    models.DurationField: "text",
    models.JSONField: "text",
}

EXCLUDED_FIELDSET_NAMES = frozenset(
    {
        "Audit",
        "Action",
    }
)

# System columns are mostly not included in the data export.
# Columns "id", "revision", "consent_version", and the
# action_* identifiers are intentionally NOT excluded.
EXCLUDED_FIELD_NAMES = frozenset(
    {
        "subject_visit",
        "related_visit",
        "consent_model",
        *[f for f in AUDIT_MODEL_FIELDS if f not in ["created", "modified"]],
    }
)


SCHEDULED_EVENT = "SE"  # scheduled event
UNSCHEDULED_EVENT = "UE"  # unscheduled event
COMMON_EVENT = "CE"
CODELIST = "CL"  # codelist
ITEM_GROUP = "IG"
ITEM = "I"
FORM = "F"

SCHEDULED_TYPE = "Scheduled"
UNSCHEDULED_TYPE = "Unscheduled"
COMMON_TYPE = "Common"

ODM_SCHEMA_PATH = Path(__file__).parent / "odm_schema" / "cdisc-odm-1.3.1" / "ODM1-3-1.xsd"
