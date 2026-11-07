"""M05 append-only human relationship decisions."""

from __future__ import annotations

import json
import hashlib
import uuid
from typing import Iterable

from .audit import append_event
from .contracts import (
    RELATION_DECISIONS,
    RELATION_STATUSES,
    canonical_json,
    require_choice,
    require_opaque_ref,
    utc_now,
)
from .database import Database
from .security import Actor
from .service import Service


class RelationService(Service):
    def decide_pair(
        self,
        left_record_id: str,
        right_record_id: str,
        relation_status: str,
        decision: str,
        evidence_refs: Iterable[str],
        actor: Actor,
    ) -> str:
        self._authorize(
            actor,
            "relation:decide",
            "decide_relation",
            "relation_pair",
            "pending",
        )
        require_choice(relation_status, RELATION_STATUSES, "relation_status")
        require_choice(decision, RELATION_DECISIONS, "decision")
        if left_record_id == right_record_id:
            raise ValueError("a relation cannot connect a record to itself")
        references = sorted(set(evidence_refs))
        for reference in references:
            require_opaque_ref(reference, "evidence_ref")
        if decision == "accepted" and not references:
            raise ValueError("accepted relation decisions require evidence references")
        pair_key = hashlib.sha256(
            "\0".join(sorted((left_record_id, right_record_id))).encode("utf-8")
        ).hexdigest()
        group_id = str(uuid.uuid4())
        created_at = utc_now()
        with self.database.connect() as connection:
            endpoints = connection.execute(
                """SELECT record_id, zone FROM records
                   WHERE record_id IN (?, ?)""",
                (left_record_id, right_record_id),
            ).fetchall()
            if len(endpoints) != 2:
                raise KeyError("both relationship endpoints must exist")
            if any(row["zone"] != "observation" for row in endpoints):
                raise ValueError("relationship review endpoints must be Observation records")
            for left, right in (
                (left_record_id, right_record_id),
                (right_record_id, left_record_id),
            ):
                connection.execute(
                    """INSERT INTO relation_events
                       (event_group_id, pair_key, left_record_id, right_record_id,
                        relation_status, decision, evidence_refs_json, decided_by, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        group_id,
                        pair_key,
                        left,
                        right,
                        relation_status,
                        decision,
                        canonical_json(references),
                        actor.name,
                        created_at,
                    ),
                )
            append_event(
                connection,
                actor,
                "decide_relation",
                "relation_pair",
                pair_key,
                "PASS",
                {
                    "event_group_id": group_id,
                    "relation_status": relation_status,
                    "decision": decision,
                    "directed_records_written": 2,
                    "evidence_refs": references,
                    "transitive_inference": False,
                },
            )
        return group_id

    def history_for_pair(
        self,
        left_record_id: str,
        right_record_id: str,
        actor: Actor,
    ) -> list[dict[str, object]]:
        self._authorize(
            actor,
            "relation:decide",
            "read_relation_history",
            "relation_pair",
            "pending",
        )
        pair_key = hashlib.sha256(
            "\0".join(sorted((left_record_id, right_record_id))).encode("utf-8")
        ).hexdigest()
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM relation_events WHERE pair_key = ? ORDER BY sequence",
                (pair_key,),
            ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "event_group_id": row["event_group_id"],
                "left_record_id": row["left_record_id"],
                "right_record_id": row["right_record_id"],
                "relation_status": row["relation_status"],
                "decision": row["decision"],
                "evidence_refs": json.loads(row["evidence_refs_json"]),
                "decided_by": row["decided_by"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

