from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    name = "edc_cdisc"
    verbose_name = "Edc CDISC"
    default_auto_field = "django.db.models.BigAutoField"
