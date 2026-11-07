"""Versioned prototype contracts shared by the local workflow modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


CONTRACT_VERSION = "broky_data.contracts.v1"
RECORD_SCHEMA = "broky_data.record.v1"
SNAPSHOT_SCHEMA = "broky_data.snapshot.v1"
ACCEPTANCE_SCHEMA = "broky_data.acceptance.v1"

ASSET_TYPES = frozenset({"image", "model_3d", "document", "other"})
DATA_ZONES = frozenset({"observation", "truth"})
SOURCE_KINDS = frozenset({"physical", "synthetic", "fast_geo", "unknown"})
AUTHORIZATION_STATUSES = frozenset(
    {"unknown", "pending", "approved", "restricted", "rejected"}
)
PHYSICAL_QUALIFICATIONS = frozenset(
    {"unknown", "not_applicable", "pending", "supported", "unsupported"}
)
TRAINING_ELIGIBILITY = frozenset(
    {"unknown", "pending", "eligible", "ineligible"}
)
ALLOWED_USES = frozenset(
    {"internal_review", "model_training", "evaluation", "internal_report", "public_release"}
)
SNAPSHOT_PURPOSES = ALLOWED_USES
RELATION_STATUSES = frozenset({"R0", "R1", "R2", "TINY_CONTACT", "UNKNOWN"})
RELATION_DECISIONS = frozenset(
    {"proposed", "accepted", "rejected", "revoked", "needs_review"}
)
RESULT_STATES = frozenset({"PASS", "FAIL", "BLOCKED"})
_OPAQUE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ContractError(ValueError):
    """Raised when a prototype contract value is malformed or unsupported."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_choice(value: str, choices: frozenset[str], field: str) -> str:
    if not isinstance(value, str) or value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ContractError(f"{field} must be one of: {allowed}")
    return value


def require_opaque_ref(value: str | None, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not _OPAQUE_REF_RE.fullmatch(value):
        raise ContractError(f"{field} must be a short opaque reference, not a path")
    if "/" in value or "\\" in value:
        raise ContractError(f"{field} must not contain path separators")
    return value


@dataclass(frozen=True)
class IntakeMetadata:
    """Non-authoritative intake fields used by the test-stage prototype."""

    asset_type: str
    media_type: str = "application/octet-stream"
    zone: str = "observation"
    source_kind: str = "unknown"
    source_ref: str | None = None

    def validate(self) -> "IntakeMetadata":
        require_choice(self.asset_type, ASSET_TYPES, "asset_type")
        require_choice(self.zone, DATA_ZONES, "zone")
        require_choice(self.source_kind, SOURCE_KINDS, "source_kind")
        if not isinstance(self.media_type, str) or "/" not in self.media_type:
            raise ContractError("media_type must be an explicit MIME type")
        require_opaque_ref(self.source_ref, "source_ref", optional=True)
        return self


@dataclass(frozen=True)
class Clearance:
    """Human-reviewed authorization and qualification decisions."""

    authorization_status: str = "unknown"
    allowed_uses: tuple[str, ...] = ()
    rights_evidence_ref: str | None = None
    physical_qualification: str = "unknown"
    physical_evidence_ref: str | None = None
    training_eligibility: str = "unknown"
    training_evidence_ref: str | None = None
    physics_claim: bool = False

    def validate(self, source_kind: str) -> "Clearance":
        require_choice(
            self.authorization_status,
            AUTHORIZATION_STATUSES,
            "authorization_status",
        )
        require_choice(
            self.physical_qualification,
            PHYSICAL_QUALIFICATIONS,
            "physical_qualification",
        )
        require_choice(
            self.training_eligibility,
            TRAINING_ELIGIBILITY,
            "training_eligibility",
        )
        if not isinstance(self.physics_claim, bool):
            raise ContractError("physics_claim must be a boolean")
        if len(set(self.allowed_uses)) != len(self.allowed_uses):
            raise ContractError("allowed_uses must not contain duplicates")
        for use in self.allowed_uses:
            require_choice(use, ALLOWED_USES, "allowed_uses item")
        require_opaque_ref(self.rights_evidence_ref, "rights_evidence_ref", optional=True)
        require_opaque_ref(
            self.physical_evidence_ref,
            "physical_evidence_ref",
            optional=True,
        )
        require_opaque_ref(
            self.training_evidence_ref,
            "training_evidence_ref",
            optional=True,
        )
        if self.authorization_status == "approved":
            if not self.allowed_uses or not self.rights_evidence_ref:
                raise ContractError(
                    "approved authorization requires allowed uses and a rights evidence reference"
                )
        if self.physical_qualification == "supported" and not self.physical_evidence_ref:
            raise ContractError(
                "supported physical qualification requires a physical evidence reference"
            )
        if self.training_eligibility == "eligible" and not self.training_evidence_ref:
            raise ContractError(
                "eligible training status requires a training evidence reference"
            )
        if source_kind == "fast_geo" and (
            self.physics_claim or self.physical_qualification == "supported"
        ):
            raise ContractError(
                "fast_geo input must not claim physical qualification or physical physics"
            )
        return self

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Record:
    record_id: str
    schema_name: str
    asset_sha256: str
    asset_size: int
    asset_type: str
    media_type: str
    zone: str
    source_kind: str
    source_ref: str | None
    authorization_status: str
    allowed_uses: tuple[str, ...]
    rights_evidence_ref: str | None
    physical_qualification: str
    physical_evidence_ref: str | None
    training_eligibility: str
    training_evidence_ref: str | None
    physics_claim: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Any) -> "Record":
        return cls(
            record_id=row["record_id"],
            schema_name=row["schema_name"],
            asset_sha256=row["asset_sha256"],
            asset_size=row["asset_size"],
            asset_type=row["asset_type"],
            media_type=row["media_type"],
            zone=row["zone"],
            source_kind=row["source_kind"],
            source_ref=row["source_ref"],
            authorization_status=row["authorization_status"],
            allowed_uses=tuple(json.loads(row["allowed_uses_json"])),
            rights_evidence_ref=row["rights_evidence_ref"],
            physical_qualification=row["physical_qualification"],
            physical_evidence_ref=row["physical_evidence_ref"],
            training_eligibility=row["training_eligibility"],
            training_evidence_ref=row["training_evidence_ref"],
            physics_claim=bool(row["physics_claim"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True)
class ValidationReceipt:
    validation_id: str
    record_id: str
    purpose: str
    outcome: str
    checks: tuple[dict[str, Any], ...]
    record_sha256: str
    validator_version: str
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "broky_data.validation.v1",
            "validation_id": self.validation_id,
            "record_id": self.record_id,
            "purpose": self.purpose,
            "outcome": self.outcome,
            "checks": list(self.checks),
            "record_sha256": self.record_sha256,
            "validator_version": self.validator_version,
            "created_at": self.created_at,
        }

