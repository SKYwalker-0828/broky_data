"""M06 rebuildable exact-cosine index adapter for small test datasets."""

from __future__ import annotations

import json
import math
import uuid
from typing import Iterable, Mapping

from .audit import append_event
from .contracts import canonical_json, json_sha256, require_opaque_ref, utc_now
from .database import Database
from .security import Actor
from .service import Service


class SearchService(Service):
    def build_index(
        self,
        snapshot_id: str,
        encoder_id: str,
        vectors: Mapping[str, Iterable[float]],
        actor: Actor,
    ) -> dict[str, object]:
        self._authorize(actor, "search:build", "build_search_index", "index", snapshot_id)
        require_opaque_ref(encoder_id, "encoder_id")
        with self.database.connect() as connection:
            snapshot = connection.execute(
                "SELECT zone FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)
            ).fetchone()
            members = connection.execute(
                "SELECT member_id FROM snapshot_members WHERE snapshot_id = ? ORDER BY member_id",
                (snapshot_id,),
            ).fetchall()
        if snapshot is None:
            raise KeyError(f"snapshot not found: {snapshot_id}")
        if snapshot["zone"] != "observation":
            raise ValueError("search indexes can only be built from Observation snapshots")
        member_ids = [row["member_id"] for row in members]
        if set(vectors) != set(member_ids):
            raise ValueError("feature keys must exactly match snapshot member IDs")
        if not member_ids:
            raise ValueError("cannot index an empty snapshot")

        normalized: dict[str, list[float]] = {}
        dimension: int | None = None
        for member_id in member_ids:
            vector = self._normalize(vectors[member_id])
            if dimension is None:
                dimension = len(vector)
            elif len(vector) != dimension:
                raise ValueError("all vectors must have the same dimension")
            normalized[member_id] = vector
        index_hash = json_sha256(
            {
                "snapshot_id": snapshot_id,
                "encoder_id": encoder_id,
                "dimension": dimension,
                "vectors": normalized,
            }
        )
        index_id = str(uuid.uuid4())
        created_at = utc_now()
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO search_indexes
                   (index_id, snapshot_id, encoder_id, dimension, index_sha256,
                    created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    index_id,
                    snapshot_id,
                    encoder_id,
                    dimension,
                    index_hash,
                    actor.name,
                    created_at,
                ),
            )
            for member_id, vector in normalized.items():
                vector_json = canonical_json(vector)
                connection.execute(
                    """INSERT INTO search_vectors
                       (index_id, snapshot_id, member_id, dimension, vector_json, vector_sha256)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        index_id,
                        snapshot_id,
                        member_id,
                        dimension,
                        vector_json,
                        json_sha256(vector),
                    ),
                )
            append_event(
                connection,
                actor,
                "build_search_index",
                "index",
                index_id,
                "PASS",
                {
                    "snapshot_id": snapshot_id,
                    "index_id": index_id,
                    "encoder_id": encoder_id,
                    "member_count": len(normalized),
                    "dimension": dimension,
                    "index_sha256": index_hash,
                    "method": "exact_cosine",
                },
            )
        return {
            "index_id": index_id,
            "snapshot_id": snapshot_id,
            "encoder_id": encoder_id,
            "member_count": len(normalized),
            "dimension": dimension,
            "index_sha256": index_hash,
            "method": "exact_cosine",
        }

    def query(
        self,
        snapshot_id: str,
        encoder_id: str,
        vector: Iterable[float],
        actor: Actor,
        limit: int = 10,
        index_id: str | None = None,
    ) -> list[dict[str, object]]:
        self._authorize(actor, "search:query", "query_search_index", "index", snapshot_id)
        require_opaque_ref(encoder_id, "encoder_id")
        if index_id is not None:
            require_opaque_ref(index_id, "index_id")
        if not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ValueError("limit must be an integer between 1 and 1000")
        query_vector = self._normalize(vector)
        with self.database.connect() as connection:
            snapshot = connection.execute(
                "SELECT zone FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)
            ).fetchone()
            selected_index = connection.execute(
                """SELECT index_id FROM search_indexes
                   WHERE snapshot_id = ? AND encoder_id = """
                + ("? AND index_id = ? " if index_id is not None else "? ")
                + "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (snapshot_id, encoder_id, index_id)
                if index_id is not None
                else (snapshot_id, encoder_id),
            ).fetchone()
            rows = connection.execute(
                """SELECT member_id, dimension, vector_json
                   FROM search_vectors
                   WHERE index_id = ?
                   ORDER BY member_id""",
                (selected_index["index_id"],) if selected_index is not None else ("",),
            ).fetchall()
        if snapshot is None:
            raise KeyError(f"snapshot not found: {snapshot_id}")
        if snapshot["zone"] != "observation":
            raise ValueError("search is restricted to Observation snapshots")
        if selected_index is None or not rows:
            raise KeyError("no index exists for this snapshot and encoder")
        if any(row["dimension"] != len(query_vector) for row in rows):
            raise ValueError("query vector dimension does not match the index")
        results = []
        for row in rows:
            stored = json.loads(row["vector_json"])
            score = sum(a * b for a, b in zip(query_vector, stored))
            results.append({"member_id": row["member_id"], "score": score})
        results.sort(key=lambda item: (-float(item["score"]), str(item["member_id"])))
        selected = results[:limit]
        with self.database.connect() as connection:
            append_event(
                connection,
                actor,
                "query_search_index",
                "index",
                selected_index["index_id"],
                "PASS",
                {
                    "snapshot_id": snapshot_id,
                    "index_id": selected_index["index_id"],
                    "encoder_id": encoder_id,
                    "result_count": len(selected),
                    "returned_member_ids": [item["member_id"] for item in selected],
                },
            )
        return selected

    @staticmethod
    def _normalize(vector: Iterable[float]) -> list[float]:
        try:
            values = list(vector)
        except TypeError as exc:
            raise ValueError("vector must be an iterable of finite numbers") from exc
        if not values:
            raise ValueError("vector must not be empty")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in values
        ):
            raise ValueError("vector values must be finite numbers")
        scale = max(abs(float(value)) for value in values)
        if scale == 0:
            raise ValueError("zero vectors cannot be cosine-normalized")
        scaled = [float(value) / scale for value in values]
        norm = math.sqrt(sum(value * value for value in scaled))
        return [value / norm for value in scaled]

