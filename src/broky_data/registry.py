"""M02 registration, source tracking, and human clearance workflow."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import uuid

from .audit import append_event
from .contracts import (
    Clearance,
    IntakeMetadata,
    RECORD_SCHEMA,
    Record,
    canonical_json,
    utc_now,
)
from .database import Database
from .security import Actor
from .service import Service


class RegistryService(Service):
    def register_bytes(
        self,
        data: bytes,
        metadata: IntakeMetadata,
        actor: Actor,
    ) -> Record:
        metadata.validate()
        permission = "truth:ingest" if metadata.zone == "truth" else "record:ingest"
        self._authorize(actor, permission, "register_asset", "record", "pending")
        receipt = self.database.asset_store(metadata.zone).put_bytes(data)
        now = utc_now()
        record_id = str(uuid.uuid4())
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO records
                   (record_id, schema_name, asset_sha256, asset_size, asset_type,
                    media_type, zone, source_kind, source_ref, authorization_status,
                    allowed_uses_json, rights_evidence_ref, physical_qualification,
                    physical_evidence_ref, training_eligibility, training_evidence_ref,
                    physics_claim, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown', '[]', NULL,
                           'unknown', NULL, 'unknown', NULL, 0, ?, ?)""",
                (
                    record_id,
                    RECORD_SCHEMA,
                    receipt.ref.sha256,
                    receipt.size_bytes,
                    metadata.asset_type,
                    metadata.media_type,
                    metadata.zone,
                    metadata.source_kind,
                    metadata.source_ref,
                    now,
                    now,
                ),
            )
            append_event(
                connection,
                actor,
                "register_asset",
                "record",
                record_id,
                "PASS",
                {
                    "zone": metadata.zone,
                    "asset_type": metadata.asset_type,
                    "source_kind": metadata.source_kind,
                    "asset_size": receipt.size_bytes,
                    "asset_sha256": receipt.ref.sha256,
                    "initial_clearance": "unknown",
                },
            )
            row = connection.execute(
                "SELECT * FROM records WHERE record_id = ?", (record_id,)
            ).fetchone()
        return Record.from_row(row)

    def register_file(
        self,
        path: str | Path,
        metadata: IntakeMetadata,
        actor: Actor,
    ) -> Record:
        metadata.validate()
        permission = "truth:ingest" if metadata.zone == "truth" else "record:ingest"
        self._authorize(actor, permission, "register_asset", "record", "pending")
        with Path(path).expanduser().open("rb") as source:
            return self._register_stream(source, metadata, actor, authorize=False)

    def _register_stream(
        self,
        source,
        metadata: IntakeMetadata,
        actor: Actor,
        *,
        authorize: bool = True,
    ) -> Record:
        metadata.validate()
        permission = "truth:ingest" if metadata.zone == "truth" else "record:ingest"
        if authorize:
            self._authorize(actor, permission, "register_asset", "record", "pending")
        receipt = self.database.asset_store(metadata.zone).put_stream(source)
        now = utc_now()
        record_id = str(uuid.uuid4())
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO records
                   (record_id, schema_name, asset_sha256, asset_size, asset_type,
                    media_type, zone, source_kind, source_ref, authorization_status,
                    allowed_uses_json, rights_evidence_ref, physical_qualification,
                    physical_evidence_ref, training_eligibility, training_evidence_ref,
                    physics_claim, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown', '[]', NULL,
                           'unknown', NULL, 'unknown', NULL, 0, ?, ?)""",
                (
                    record_id,
                    RECORD_SCHEMA,
                    receipt.ref.sha256,
                    receipt.size_bytes,
                    metadata.asset_type,
                    metadata.media_type,
                    metadata.zone,
                    metadata.source_kind,
                    metadata.source_ref,
                    now,
                    now,
                ),
            )
            append_event(
                connection,
                actor,
                "register_asset",
                "record",
                record_id,
                "PASS",
                {
                    "zone": metadata.zone,
                    "asset_type": metadata.asset_type,
                    "source_kind": metadata.source_kind,
                    "asset_size": receipt.size_bytes,
                    "asset_sha256": receipt.ref.sha256,
                    "initial_clearance": "unknown",
                },
            )
            row = connection.execute(
                "SELECT * FROM records WHERE record_id = ?", (record_id,)
            ).fetchone()
        return Record.from_row(row)

    def review_clearance(
        self,
        record_id: str,
        clearance: Clearance,
        actor: Actor,
    ) -> Record:
        self._authorize(actor, "record:review", "review_clearance", "record", record_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM records WHERE record_id = ?", (record_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"record not found: {record_id}")
            clearance.validate(row["source_kind"])
            before = {
                "authorization_status": row["authorization_status"],
                "allowed_uses": json.loads(row["allowed_uses_json"]),
                "rights_evidence_ref": row["rights_evidence_ref"],
                "physical_qualification": row["physical_qualification"],
                "physical_evidence_ref": row["physical_evidence_ref"],
                "training_eligibility": row["training_eligibility"],
                "training_evidence_ref": row["training_evidence_ref"],
                "physics_claim": bool(row["physics_claim"]),
            }
            now = utc_now()
            connection.execute(
                """UPDATE records SET authorization_status = ?, allowed_uses_json = ?,
                   rights_evidence_ref = ?, physical_qualification = ?,
                   physical_evidence_ref = ?, training_eligibility = ?,
                   training_evidence_ref = ?, physics_claim = ?, updated_at = ?
                   WHERE record_id = ?""",
                (
                    clearance.authorization_status,
                    canonical_json(sorted(clearance.allowed_uses)),
                    clearance.rights_evidence_ref,
                    clearance.physical_qualification,
                    clearance.physical_evidence_ref,
                    clearance.training_eligibility,
                    clearance.training_evidence_ref,
                    int(clearance.physics_claim),
                    now,
                    record_id,
                ),
            )
            append_event(
                connection,
                actor,
                "review_clearance",
                "record",
                record_id,
                "PASS",
                {
                    "before": before,
                    "after": {
                        "authorization_status": clearance.authorization_status,
                        "allowed_uses": sorted(clearance.allowed_uses),
                        "physical_qualification": clearance.physical_qualification,
                        "physical_evidence_ref": clearance.physical_evidence_ref,
                        "training_eligibility": clearance.training_eligibility,
                        "training_evidence_ref": clearance.training_evidence_ref,
                        "rights_evidence_ref": clearance.rights_evidence_ref,
                        "physics_claim": clearance.physics_claim,
                    },
                    "evidence_refs": [
                        ref
                        for ref in (
                            clearance.rights_evidence_ref,
                            clearance.physical_evidence_ref,
                            clearance.training_evidence_ref,
                        )
                        if ref is not None
                    ],
                },
            )
            updated = connection.execute(
                "SELECT * FROM records WHERE record_id = ?", (record_id,)
            ).fetchone()
        return Record.from_row(updated)

    def get_record(self, record_id: str, actor: Actor) -> Record:
        if actor.role == "evaluator":
            self._authorize(
                actor,
                "record:read_truth_registry",
                "read_record",
                "record",
                record_id,
            )
            zone_filter = " AND zone = 'truth'"
        elif actor.role == "admin":
            zone_filter = ""
        else:
            self._authorize(
                actor,
                "record:read_registry",
                "read_record",
                "record",
                record_id,
            )
            zone_filter = " AND zone = 'observation'"
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM records WHERE record_id = ?" + zone_filter,
                (record_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"record not found: {record_id}")
        return Record.from_row(row)


def record_from_connection(
    connection: sqlite3.Connection, record_id: str
) -> Record:
    row = connection.execute(
        "SELECT * FROM records WHERE record_id = ?", (record_id,)
    ).fetchone()
    if row is None:
        raise KeyError(f"record not found: {record_id}")
    return Record.from_row(row)

