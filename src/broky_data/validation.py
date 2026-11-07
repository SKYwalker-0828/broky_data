"""M03 deterministic structural, reference, rights, and eligibility checks."""

from __future__ import annotations

import json
import uuid

from .audit import append_event
from .contracts import (
    RESULT_STATES,
    SNAPSHOT_PURPOSES,
    Clearance,
    IntakeMetadata,
    Record,
    ValidationReceipt,
    json_sha256,
    require_choice,
    utc_now,
)
from .database import Database
from .registry import record_from_connection
from .security import Actor
from .service import Service


VALIDATOR_VERSION = "broky_data.validator.v1"


class ValidationService(Service):
    def validate_record(
        self,
        record_id: str,
        purpose: str,
        actor: Actor,
    ) -> ValidationReceipt:
        self._authorize(actor, "validation:run", "validate_record", "record", record_id)
        require_choice(purpose, SNAPSHOT_PURPOSES, "purpose")
        truth_capable = actor.role in {"admin", "evaluator"}
        with self.database.connect() as connection:
            if truth_capable:
                record = record_from_connection(connection, record_id)
            else:
                row = connection.execute(
                    "SELECT * FROM records WHERE record_id = ? AND zone = 'observation'",
                    (record_id,),
                ).fetchone()
                if row is None:
                    self._authorize(
                        actor,
                        "truth:validate",
                        "validate_truth_record",
                        "record",
                        record_id,
                    )
                    raise KeyError(f"record not found: {record_id}")
                record = Record.from_row(row)
        if record.zone == "truth":
            self._authorize(
                actor,
                "truth:validate",
                "validate_truth_record",
                "record",
                record_id,
            )

        checks: list[dict[str, str]] = []
        failure = False
        blocked = False

        def add(code: str, status: str, detail: str) -> None:
            nonlocal failure, blocked
            if status == "FAIL":
                failure = True
            elif status == "BLOCKED":
                blocked = True
            checks.append({"code": code, "status": status, "detail": detail})

        try:
            IntakeMetadata(
                asset_type=record.asset_type,
                media_type=record.media_type,
                zone=record.zone,
                source_kind=record.source_kind,
                source_ref=record.source_ref,
            ).validate()
            Clearance(
                authorization_status=record.authorization_status,
                allowed_uses=record.allowed_uses,
                rights_evidence_ref=record.rights_evidence_ref,
                physical_qualification=record.physical_qualification,
                physical_evidence_ref=record.physical_evidence_ref,
                training_eligibility=record.training_eligibility,
                training_evidence_ref=record.training_evidence_ref,
                physics_claim=record.physics_claim,
            ).validate(record.source_kind)
        except ValueError as exc:
            add("record_contract", "FAIL", str(exc))
        else:
            add("record_contract", "PASS", record.schema_name)

        nonempty = isinstance(record.asset_size, int) and record.asset_size > 0
        add(
            "asset_size",
            "PASS" if nonempty else "FAIL",
            "asset contains bytes" if nonempty else "empty assets are not accepted",
        )

        try:
            intact = self.database.asset_store(record.zone).verify(
                self._asset_ref(record.asset_sha256)
            )
        except (OSError, ValueError, RuntimeError):
            intact = False
        add(
            "asset_integrity",
            "PASS" if intact else "FAIL",
            "SHA-256 matches stored bytes" if intact else "asset missing or hash mismatch",
        )

        authorized = (
            record.authorization_status == "approved" and purpose in record.allowed_uses
        )
        add(
            "use_authorization",
            "PASS" if authorized else "BLOCKED",
            "approved for requested use" if authorized else "authorization or requested-use approval is missing",
        )

        zone_ok = record.zone != "truth" or purpose == "evaluation"
        add(
            "zone_purpose_boundary",
            "PASS" if zone_ok else "BLOCKED",
            "zone and purpose are compatible" if zone_ok else "Truth/GT records are evaluation-only",
        )

        training_ok = purpose != "model_training" or (
            record.zone == "observation"
            and record.training_eligibility == "eligible"
        )
        add(
            "training_eligibility",
            "PASS" if training_ok else "BLOCKED",
            "approved observation training record"
            if training_ok
            else "training requires an eligible Observation record",
        )

        fast_geo_ok = not (record.source_kind == "fast_geo" and record.physics_claim)
        add(
            "fast_geo_physics_claim",
            "PASS" if fast_geo_ok else "FAIL",
            "FAST GEO is not represented as physical evidence",
        )

        outcome = "FAIL" if failure else "BLOCKED" if blocked else "PASS"
        require_choice(outcome, RESULT_STATES, "outcome")
        created_at = utc_now()
        validation_id = str(uuid.uuid4())
        record_fingerprint = json_sha256(
            {
                "schema": record.schema_name,
                "record_id": record.record_id,
                "asset_sha256": record.asset_sha256,
                "zone": record.zone,
                "source_kind": record.source_kind,
                "authorization_status": record.authorization_status,
                "allowed_uses": sorted(record.allowed_uses),
                "physical_qualification": record.physical_qualification,
                "training_eligibility": record.training_eligibility,
                "physics_claim": record.physics_claim,
            }
        )
        receipt = ValidationReceipt(
            validation_id=validation_id,
            record_id=record_id,
            purpose=purpose,
            outcome=outcome,
            checks=tuple(checks),
            record_sha256=record_fingerprint,
            validator_version=VALIDATOR_VERSION,
            created_at=created_at,
        )
        receipt_dict = receipt.as_dict()
        receipt_json = json.dumps(
            receipt_dict,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO validation_receipts
                   (validation_id, record_id, purpose, outcome, receipt_json,
                    receipt_sha256, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    validation_id,
                    record_id,
                    purpose,
                    outcome,
                    receipt_json,
                    json_sha256(receipt_dict),
                    created_at,
                ),
            )
            append_event(
                connection,
                actor,
                "validate_record",
                "record",
                record_id,
                outcome,
                {
                    "validation_id": validation_id,
                    "purpose": purpose,
                    "record_sha256": record_fingerprint,
                    "failed_checks": [c["code"] for c in checks if c["status"] == "FAIL"],
                    "blocked_checks": [c["code"] for c in checks if c["status"] == "BLOCKED"],
                },
            )
        return receipt

    @staticmethod
    def _asset_ref(digest: str):
        from .asset_store import AssetRef

        return AssetRef(digest)

