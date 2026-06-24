from functools import cached_property

from lxml import etree

from .clinical_data_serializer import ClinicalDataSerializer
from .metadata_serializer import MetadataSerializer
from .visit_schedule_serializer import VisitScheduleSerializer


class SnapshotSerializer(VisitScheduleSerializer):
    file_type = "Snapshot"

    def to_etree(self) -> etree._Element:
        root = super().to_etree()  # fresh <ODM>
        root.append(self.metadata_serializer.build())  # <Study>
        root.append(self.clinical_data_serializer.build())  # <ClinicalData>
        return root

    @cached_property
    def metadata_serializer(self):
        return self._make(MetadataSerializer)

    @cached_property
    def clinical_data_serializer(self):
        return self._make(ClinicalDataSerializer)

    def _make(self, cls):
        return cls(
            edc_module_name=self.edc_module_name,
            protocol_oid=self.protocol_oid,
            visit_schedule=self.visit_schedule,
            subject_identifiers=self.subject_identifiers,
            include_nulls=self.include_nulls,
        )
