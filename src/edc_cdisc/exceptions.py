from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db import models


class ModelAdminNotFoundError(Exception):
    def __init__(self, model: type[models.Model]) -> None:
        self.msg = f"ModelAdmin not found. See modelr {model._meta.label_lower}."
        super().__init__(self.msg)


class ModelAdminMissingFieldsetsError(Exception):
    def __init__(self, model: type[models.Model]) -> None:
        self.msg = (
            f"Fieldsets attribute not found. See ModelAdmin for {model._meta.label_lower}."
        )
        super().__init__(self.msg)


class ProtocolSerializerError(Exception):
    pass


class NegativeVisitCodeSequenceError(Exception):
    def __init__(self) -> None:
        self.msg = "Negative visit_code_sequence detected."
        super().__init__(self.msg)
