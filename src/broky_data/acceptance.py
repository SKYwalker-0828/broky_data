"""M09 quality/function checks and machine-readable acceptance receipts."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import uuid
from typing import Iterable, Mapping

from .audit import append_event
from .contracts import (
    ACCEPTANCE_SCHEMA,
    RESULT_STATES,
    canonical_json,
    json_sha256,
    require_choice,
    require_opaque_ref,
    utc_now,
)
from .database import Database
from .security import Actor
from .service import Service


class AcceptanceService(Service):
    def create_receipt(
        self,
        scope: str,
        quality_checks: Iterable[Mapping[str, str]],
        functionality_checks: Iterable[Mapping[str, str]],
        actor: Actor,
    ) -> dict[str, object]:
        self._authorize(actor, "acceptance:create", "create_acceptance_receipt", "receipt", "pending")
        require_opaque_ref(scope, "scope")
        quality = self._normalize_checks(quality_checks, "quality_checks")
        functionality = self._normalize_checks(
            functionality_checks, "functionality_checks"
        )
        if not quality or not functionality:
            raise ValueError("quality and functionality check groups must both be non-empty")
        quality_result = self._group_result(quality)
        functionality_result = self._group_result(functionality)
        overall = self._group_result(
            [{"status": quality_result}, {"status": functionality_result}]
        )
        receipt_id = str(uuid.uuid4())
        created_at = utc_now()
        receipt: dict[str, object] = {
            "schema": ACCEPTANCE_SCHEMA,
            "schema_version": 1,
            "receipt_id": receipt_id,
            "scope": scope,
            "created_at": created_at,
            "created_by": actor.name,
            "quality": {"result": quality_result, "checks": quality},
            "functionality": {
                "result": functionality_result,
                "checks": functionality,
            },
            "overall_result": overall,
            "interpretation": "仅反映工作流证据，不证明物理或考古真实性。",
        }
        receipt_json = canonical_json(receipt)
        receipt_hash = json_sha256(receipt)
        target = self.database.receipt_root / f"{receipt_id}.json"
        fd, temporary = tempfile.mkstemp(prefix="receipt-", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(receipt_json)
                stream.flush()
                os.fsync(stream.fileno())
            with self.database.connect() as connection:
                connection.execute(
                    """INSERT INTO acceptance_receipts
                       (receipt_id, receipt_json, receipt_sha256, created_by, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (receipt_id, receipt_json, receipt_hash, actor.name, created_at),
                )
                append_event(
                    connection,
                    actor,
                    "create_acceptance_receipt",
                    "receipt",
                    receipt_id,
                    overall,
                    {
                        "receipt_sha256": receipt_hash,
                        "quality_result": quality_result,
                        "functionality_result": functionality_result,
                    },
                )
                os.replace(temporary, target)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            Path(temporary).unlink(missing_ok=True)
        return {**receipt, "receipt_sha256": receipt_hash, "path": str(target)}

    @staticmethod
    def _normalize_checks(
        checks: Iterable[Mapping[str, str]], field: str
    ) -> list[dict[str, str | None]]:
        normalized: list[dict[str, str | None]] = []
        seen: set[str] = set()
        for item in checks:
            check_id = item.get("check_id")
            status = item.get("status")
            evidence_ref = item.get("evidence_ref")
            require_opaque_ref(check_id, f"{field}.check_id")
            require_choice(status, RESULT_STATES, f"{field}.status")
            if check_id in seen:
                raise ValueError(f"duplicate {field} check_id: {check_id}")
            seen.add(check_id)
            if evidence_ref is not None:
                require_opaque_ref(evidence_ref, f"{field}.evidence_ref")
            if status in {"PASS", "FAIL"} and evidence_ref is None:
                raise ValueError(f"{status} check {check_id} requires an evidence_ref")
            normalized.append(
                {
                    "check_id": check_id,
                    "status": status,
                    "evidence_ref": evidence_ref,
                }
            )
        return normalized

    @staticmethod
    def _group_result(checks: list[Mapping[str, str | None]]) -> str:
        states = {check["status"] for check in checks}
        if "FAIL" in states:
            return "FAIL"
        if "BLOCKED" in states:
            return "BLOCKED"
        return "PASS"

