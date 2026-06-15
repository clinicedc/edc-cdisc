from django.db import models
from django_audit_fields.constants import AUDIT_MODEL_FIELDS

ODM_NAMESPACE = "http://www.cdisc.org/ns/odm/v1.3"
ODM_VERSION = "1.3.1"

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

# System/provenance columns that must never appear in a data export.
# AUDIT_MODEL_FIELDS = created, modified, user_created, user_modified,
# hostname_*, device_*, locale_* (the django_audit_fields system columns).
# "consent_model" is consent provenance, not a CRF answer. Note that
# "id", "revision", "consent_version", and the action_* identifiers are
# intentionally NOT excluded.
EXCLUDED_FIELD_NAMES = frozenset(
    {
        "subject_visit",
        "related_visit",
        "consent_model",
        *AUDIT_MODEL_FIELDS,
    }
)
