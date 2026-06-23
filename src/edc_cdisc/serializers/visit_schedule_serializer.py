from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from django.apps import apps as django_apps
from django.db.models import Manager
from edc_visit_schedule.visit import Visit

from ..constants import COMMON_EVENT, SCHEDULED_EVENT, UNSCHEDULED_EVENT
from ..utils import oid
from .serializer import Serializer

if TYPE_CHECKING:
    from collections.abc import Iterable

    from edc_visit_schedule.visit_schedule import VisitSchedule


class RelatedVisitProtocol(Protocol):
    id: uuid.UUID
    subject_identifier: str
    report_datetime: datetime
    reason: str
    visit_schedule_name: str
    schedule_name: str
    visit_code: str
    visit_code_sequence: int

    objects: Manager
    visit: Visit
    # add only what you actually access


class VisitScheduleSerializer(Serializer):
    def __init__(
        self,
        *args,
        visit_schedule: VisitSchedule,
        subject_identifiers: Iterable[str] | None = None,
        include_nulls: bool | None = None,
        **kwargs,
    ):
        self.visit_schedule = visit_schedule
        self.subject_identifiers = subject_identifiers
        self.include_nulls: bool = False if include_nulls is None else include_nulls
        super().__init__(*args, **kwargs)

    @staticmethod
    def scheduled_event_oid(visit_code: str) -> str:
        return oid(SCHEDULED_EVENT, visit_code)

    @staticmethod
    def unscheduled_event_oid(visit_code: str) -> str:
        return oid(UNSCHEDULED_EVENT, visit_code)

    @staticmethod
    def common_event_oid(model: str) -> str:
        return oid(COMMON_EVENT, model)

    @property
    def related_visit_model_cls(self) -> type[RelatedVisitProtocol]:
        return self.visit_schedule.visit_model_cls

    def get_common_models(self) -> list[str]:
        # Skip unset or abstract/unregistered models (e.g. an abstract
        # death_report_model) — that's normal config, not bad state.
        return [
            model
            for model in [
                self.visit_schedule.death_report_model,
                self.visit_schedule.offstudy_model,
            ]
            if model and self._model_exists(model)
        ]

    @staticmethod
    def _model_exists(model: str) -> bool:
        try:
            django_apps.get_model(model)
        except LookupError:
            return False
        return True
