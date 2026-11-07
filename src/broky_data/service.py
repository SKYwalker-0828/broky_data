"""Shared service authorization and audit helpers."""

from __future__ import annotations

from .database import Database
from .security import AccessPolicy, Actor, PermissionDenied


class Service:
    def __init__(self, database: Database) -> None:
        self.database = database

    def _authorize(
        self,
        actor: Actor,
        permission: str,
        action: str,
        entity_type: str,
        entity_id: str,
    ) -> None:
        try:
            AccessPolicy.require(actor, permission)
        except (PermissionDenied, ValueError):
            try:
                actor.validate()
            except ValueError:
                raise
            from .audit import append_event

            with self.database.connect() as connection:
                append_event(
                    connection,
                    actor,
                    action,
                    entity_type,
                    entity_id,
                    "DENIED",
                    {"permission": permission},
                )
            raise

