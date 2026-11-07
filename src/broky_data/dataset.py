"""M04 immutable snapshots with separate Observation and Truth paths."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import uuid
from typing import Any, Iterable

from .asset_store import AssetRef
from .audit import append_event
from .contracts import (
    DATA_ZONES,
    SNAPSHOT_PURPOSES,
    SNAPSHOT_SCHEMA,
    canonical_json,
    json_sha256,
    require_choice,
    require_opaque_ref,
    utc_now,
)
from .database import Database
from .registry import record_from_connection
from .security import Actor
from .service import Service
from .validation import ValidationService


class SnapshotRejected(RuntimeError):
    def __init__(self, results: list[dict[str, str]]) -> None:
        self.results = results
        summary = ", ".join(
            f"{result['record_id']}={result['outcome']}" for result in results
        )
        super().__init__(f"snapshot rejected; every member must validate: {summary}")


class DatasetService(Service):
    def __init__(self, database: Database, validator: ValidationService) -> None:
        super().__init__(database)
        self.validator = validator

    def create_snapshot(
        self,
        record_ids: Iterable[str],
        zone: str,
        purpose: str,
        actor: Actor,
    ) -> dict[str, Any]:
        require_choice(zone, DATA_ZONES, "zone")
        require_choice(purpose, SNAPSHOT_PURPOSES, "purpose")
        permission = (
            "snapshot:create_truth" if zone == "truth" else "snapshot:create_observation"
        )
        self._authorize(actor, permission, "create_snapshot", "snapshot", "pending")
        ordered_ids = list(record_ids)
        if not ordered_ids:
            raise ValueError("a snapshot must contain at least one record")
        if len(ordered_ids) != len(set(ordered_ids)):
            raise ValueError("a snapshot must not contain duplicate record IDs")
        if zone == "truth" and purpose != "evaluation":
            raise ValueError("Truth/GT snapshots are restricted to evaluation purpose")
        if purpose == "model_training" and zone != "observation":
            raise ValueError("model training snapshots must use the Observation zone")

        validation_results: list[dict[str, str]] = []
        records = []
        try:
            for record_id in ordered_ids:
                record = self._get_record(record_id)
                if record.zone != zone:
                    validation_results.append(
                        {"record_id": record_id, "outcome": "BLOCKED"}
                    )
                    continue
                receipt = self.validator.validate_record(record_id, purpose, actor)
                validation_results.append(
                    {"record_id": record_id, "outcome": receipt.outcome}
                )
                records.append(record)
        except Exception as exc:
            with self.database.connect() as connection:
                append_event(
                    connection,
                    actor,
                    "create_snapshot",
                    "snapshot",
                    "pending",
                    "FAIL",
                    {"reason": type(exc).__name__, "validated_records": validation_results},
                )
            raise
        if len(records) != len(ordered_ids) or any(
            result["outcome"] != "PASS" for result in validation_results
        ):
            with self.database.connect() as connection:
                append_event(
                    connection,
                    actor,
                    "create_snapshot",
                    "snapshot",
                    "pending",
                    "BLOCKED",
                    {"validation_results": validation_results},
                )
            raise SnapshotRejected(validation_results)

        snapshot_id = str(uuid.uuid4())
        created_at = utc_now()
        members = [
            {"member_id": str(uuid.uuid4())}
            for _ in records
        ]
        manifest = {
            "schema": SNAPSHOT_SCHEMA,
            "schema_version": 1,
            "snapshot_id": snapshot_id,
            "zone": zone,
            "purpose": purpose,
            "created_at": created_at,
            "member_ids": [item["member_id"] for item in members],
        }
        manifest_json = canonical_json(manifest)
        manifest_hash = json_sha256(manifest)
        snapshot_path = (
            self.database.snapshot_root / zone / snapshot_id / "manifest.json"
        )
        snapshot_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(prefix="manifest-", dir=snapshot_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(manifest_json)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                with self.database.connect() as connection:
                    connection.execute(
                        """INSERT INTO snapshots
                           (snapshot_id, schema_name, zone, purpose, manifest_json,
                            manifest_sha256, created_by, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            snapshot_id,
                            SNAPSHOT_SCHEMA,
                            zone,
                            purpose,
                            manifest_json,
                            manifest_hash,
                            actor.name,
                            created_at,
                        ),
                    )
                    for member, record in zip(members, records):
                        connection.execute(
                            """INSERT INTO snapshot_members
                               (snapshot_id, member_id, record_id, asset_sha256)
                               VALUES (?, ?, ?, ?)""",
                            (
                                snapshot_id,
                                member["member_id"],
                                record.record_id,
                                record.asset_sha256,
                            ),
                        )
                    append_event(
                        connection,
                        actor,
                        "create_snapshot",
                        "snapshot",
                        snapshot_id,
                        "PASS",
                        {
                            "zone": zone,
                            "purpose": purpose,
                            "member_count": len(records),
                            "manifest_sha256": manifest_hash,
                        },
                    )
                    os.replace(temporary_path, snapshot_path)
            except Exception:
                snapshot_path.unlink(missing_ok=True)
                raise
        finally:
            Path(temporary_path).unlink(missing_ok=True)
        return {
            **manifest,
            "manifest_sha256": manifest_hash,
            "manifest_path": str(snapshot_path),
        }

    def get_snapshot(self, snapshot_id: str, actor: Actor) -> dict[str, Any]:
        truth_capable = actor.role in {"admin", "evaluator"}
        if not truth_capable:
            self._authorize(
                actor,
                "dataset:read_observation",
                "read_snapshot",
                "snapshot",
                snapshot_id,
            )
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM snapshots WHERE snapshot_id = ?"
                + ("" if truth_capable else " AND zone = 'observation'"),
                (snapshot_id,),
            ).fetchone()
        if row is None:
            if not truth_capable:
                self._authorize(
                    actor,
                    "dataset:read_truth",
                    "read_snapshot",
                    "snapshot",
                    snapshot_id,
                )
            raise KeyError(f"snapshot not found: {snapshot_id}")
        permission = (
            "dataset:read_truth"
            if row["zone"] == "truth"
            else "dataset:read_observation"
        )
        self._authorize(actor, permission, "read_snapshot", "snapshot", snapshot_id)
        manifest = json.loads(row["manifest_json"])
        with self.database.connect() as connection:
            append_event(
                connection,
                actor,
                "read_snapshot",
                "snapshot",
                snapshot_id,
                "PASS",
                {"zone": row["zone"], "manifest_sha256": row["manifest_sha256"]},
            )
        return {**manifest, "manifest_sha256": row["manifest_sha256"]}

    def read_member_bytes(
        self,
        snapshot_id: str,
        member_id: str,
        actor: Actor,
    ) -> bytes:
        require_opaque_ref(member_id, "member_id")
        truth_capable = actor.role in {"admin", "evaluator"}
        if not truth_capable:
            self._authorize(
                actor,
                "dataset:read_observation",
                "read_member",
                "snapshot",
                snapshot_id,
            )
        with self.database.connect() as connection:
            snapshot = connection.execute(
                "SELECT zone FROM snapshots WHERE snapshot_id = ?"
                + ("" if truth_capable else " AND zone = 'observation'"),
                (snapshot_id,),
            ).fetchone()
            if snapshot is None:
                if not truth_capable:
                    self._authorize(
                        actor,
                        "dataset:read_truth",
                        "read_member",
                        "snapshot",
                        snapshot_id,
                    )
                raise KeyError(f"snapshot not found: {snapshot_id}")
            permission = (
                "dataset:read_truth"
                if snapshot["zone"] == "truth"
                else "dataset:read_observation"
            )
            member = connection.execute(
                """SELECT asset_sha256 FROM snapshot_members
                   WHERE snapshot_id = ? AND member_id = ?""",
                (snapshot_id, member_id),
            ).fetchone()
        self._authorize(actor, permission, "read_member", "snapshot", snapshot_id)
        if member is None:
            raise KeyError(f"member not found in snapshot: {member_id}")
        with self.database.asset_store(snapshot["zone"]).open(
            AssetRef(member["asset_sha256"])
        ) as stream:
            content = stream.read()
        with self.database.connect() as connection:
            append_event(
                connection,
                actor,
                "read_snapshot_member",
                "snapshot_member",
                member_id,
                "PASS",
                {"snapshot_id": snapshot_id, "zone": snapshot["zone"]},
            )
        return content

    def create_evaluation_join(
        self,
        observation_snapshot_id: str,
        truth_snapshot_id: str,
        evidence_ref: str,
        actor: Actor,
    ) -> dict[str, str]:
        self._authorize(
            actor,
            "dataset:join",
            "create_evaluation_join",
            "evaluation_join",
            "pending",
        )
        require_opaque_ref(evidence_ref, "evidence_ref")
        with self.database.connect() as connection:
            observation = connection.execute(
                "SELECT zone, purpose FROM snapshots WHERE snapshot_id = ?",
                (observation_snapshot_id,),
            ).fetchone()
            truth = connection.execute(
                "SELECT zone, purpose FROM snapshots WHERE snapshot_id = ?",
                (truth_snapshot_id,),
            ).fetchone()
            if observation is None or truth is None:
                raise KeyError("both evaluation snapshots must exist")
            if observation["zone"] != "observation" or truth["zone"] != "truth":
                raise ValueError("join requires one Observation and one Truth snapshot")
            if observation["purpose"] != "evaluation" or truth["purpose"] != "evaluation":
                raise ValueError("both snapshots must be frozen for evaluation")
            join_id = str(uuid.uuid4())
            created_at = utc_now()
            connection.execute(
                """INSERT INTO evaluation_joins
                   (join_id, observation_snapshot_id, truth_snapshot_id,
                    evidence_ref, authorized_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    join_id,
                    observation_snapshot_id,
                    truth_snapshot_id,
                    evidence_ref,
                    actor.name,
                    created_at,
                ),
            )
            append_event(
                connection,
                actor,
                "create_evaluation_join",
                "evaluation_join",
                join_id,
                "PASS",
                {
                    "observation_snapshot_id": observation_snapshot_id,
                    "truth_snapshot_id": truth_snapshot_id,
                    "evidence_ref": evidence_ref,
                },
            )
        return {"join_id": join_id, "created_at": created_at}

    def _get_record(self, record_id: str):
        with self.database.connect() as connection:
            return record_from_connection(connection, record_id)

