"""Composition root for the modular local test-stage workflow."""

from __future__ import annotations

from os import PathLike

from .acceptance import AcceptanceService
from .analytics import AnalyticsService
from .audit import AuditService
from .dataset import DatasetService
from .database import Database
from .outputs import OutputService
from .registry import RegistryService
from .relations import RelationService
from .search import SearchService
from .validation import ValidationService


class BrokyData:
    """Wire replaceable modules around the local SQLite/file adapters."""

    def __init__(self, root: str | PathLike[str]) -> None:
        self.database = Database(root)
        self.registry = RegistryService(self.database)
        self.validation = ValidationService(self.database)
        self.datasets = DatasetService(self.database, self.validation)
        self.relations = RelationService(self.database)
        self.search = SearchService(self.database)
        self.analytics = AnalyticsService(self.database)
        self.outputs = OutputService(self.database)
        self.acceptance = AcceptanceService(self.database)
        self.audit = AuditService(self.database)

