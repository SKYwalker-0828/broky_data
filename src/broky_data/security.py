"""Prototype role checks. Authentication is intentionally outside this module."""

from __future__ import annotations

from dataclasses import dataclass


class PermissionDenied(PermissionError):
    """Raised when a role is not allowed to perform an operation."""


@dataclass(frozen=True)
class Actor:
    name: str
    role: str

    def validate(self) -> "Actor":
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 128:
            raise ValueError("actor name must contain 1 to 128 characters")
        if not isinstance(self.role, str) or self.role not in ROLE_PERMISSIONS:
            raise ValueError(f"unknown role: {self.role}")
        return self


ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({"*"}),
    "registrar": frozenset(
        {"record:ingest", "record:read_registry", "validation:run"}
    ),
    "curator": frozenset(
        {
            "record:ingest",
            "record:read_registry",
            "record:review",
            "validation:run",
            "snapshot:create_observation",
            "relation:decide",
            "acceptance:create",
        }
    ),
    "reviewer": frozenset(
        {"record:read_registry", "validation:run", "relation:decide"}
    ),
    "analyst": frozenset(
        {
            "snapshot:create_observation",
            "dataset:read_observation",
            "validation:run",
            "search:build",
            "search:query",
            "analytics:read_observation",
            "output:internal",
        }
    ),
    "model": frozenset({"dataset:read_observation", "search:query"}),
    "evaluator": frozenset(
        {
            "truth:ingest",
            "record:read_truth_registry",
            "truth:validate",
            "validation:run",
            "snapshot:create_observation",
            "snapshot:create_truth",
            "dataset:read_observation",
            "dataset:read_truth",
            "dataset:join",
        }
    ),
    "auditor": frozenset(
        {"analytics:read_all", "audit:read", "acceptance:create"}
    ),
    "publisher": frozenset({"output:internal", "output:public"}),
}


class AccessPolicy:
    """Fail-closed authorization for local prototype operations."""

    @staticmethod
    def require(actor: Actor, permission: str) -> None:
        actor.validate()
        permissions = ROLE_PERMISSIONS[actor.role]
        if "*" not in permissions and permission not in permissions:
            raise PermissionDenied(
                f"role {actor.role!r} is not permitted to perform {permission!r}"
            )

