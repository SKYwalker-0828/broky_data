"""Append-only, hash-chained local action receipts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import uuid
from typing import Any

from .contracts import canonical_json, json_sha256, utc_now
from .database import Database
from .security import Actor
from .service import Service


_GENESIS = "0" * 64


def append_event(
    connection: Any,
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: str,
    outcome: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    previous = connection.execute(
        "SELECT sequence, event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
    ).fetchone()
    sequence = 1 if previous is None else previous["sequence"] + 1
    previous_hash = _GENESIS if previous is None else previous["event_hash"]
    event = {
        "sequence": sequence,
        "event_id": str(uuid.uuid4()),
        "created_at": utc_now(),
        "actor_name": actor.name,
        "actor_role": actor.role,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "outcome": outcome,
        "details": details,
        "previous_hash": previous_hash,
    }
    event_hash = json_sha256(event)
    connection.execute(
        """INSERT INTO audit_events
           (sequence, event_id, created_at, actor_name, actor_role, action,
            entity_type, entity_id, outcome, details_json, previous_hash, event_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            sequence,
            event["event_id"],
            event["created_at"],
            actor.name,
            actor.role,
            action,
            entity_type,
            entity_id,
            outcome,
            canonical_json(details),
            previous_hash,
            event_hash,
        ),
    )
    event["event_hash"] = event_hash
    return event


def event_from_row(row: Any) -> dict[str, Any]:
    return {
        "sequence": row["sequence"],
        "event_id": row["event_id"],
        "created_at": row["created_at"],
        "actor_name": row["actor_name"],
        "actor_role": row["actor_role"],
        "action": row["action"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "outcome": row["outcome"],
        "details": json.loads(row["details_json"]),
        "previous_hash": row["previous_hash"],
        "event_hash": row["event_hash"],
    }


class AuditService(Service):
    def verify_chain(self, actor: Actor) -> dict[str, Any]:
        self._authorize(actor, "audit:read", "verify_audit_chain", "audit", "chain")
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events ORDER BY sequence"
            ).fetchall()
        expected_previous = _GENESIS
        checked = 0
        for expected_sequence, row in enumerate(rows, start=1):
            try:
                event = event_from_row(row)
            except (TypeError, ValueError, json.JSONDecodeError):
                return {"valid": False, "checked": checked, "reason": "malformed_event"}
            if event["sequence"] != expected_sequence:
                return {"valid": False, "checked": checked, "reason": "sequence_gap"}
            if event["previous_hash"] != expected_previous:
                return {"valid": False, "checked": checked, "reason": "previous_hash_mismatch"}
            claimed_hash = event.pop("event_hash")
            if json_sha256(event) != claimed_hash:
                return {"valid": False, "checked": checked, "reason": "event_hash_mismatch"}
            expected_previous = claimed_hash
            checked += 1
        with self.database.connect() as connection:
            append_event(
                connection,
                actor,
                "verify_audit_chain",
                "audit",
                "chain",
                "PASS",
                {"checked": checked},
            )
        return {"valid": True, "checked": checked, "head_hash": expected_previous}

    def export_jsonl(self, destination: str | Path, actor: Actor) -> Path:
        self._authorize(actor, "audit:read", "export_audit", "audit", "events")
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events ORDER BY sequence"
            ).fetchall()
        target = Path(destination).expanduser().absolute()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(canonical_json(event_from_row(row)) + "\n" for row in rows)
        fd, temporary = tempfile.mkstemp(prefix="audit-", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            Path(temporary).replace(target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        with self.database.connect() as connection:
            append_event(
                connection,
                actor,
                "export_audit",
                "audit",
                "events",
                "PASS",
                {"count": len(rows)},
            )
        return target

