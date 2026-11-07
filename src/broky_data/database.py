"""SQLite metadata store for the local test-stage deployment."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
from typing import Iterator
import uuid

from .asset_store import LocalAssetStore
from .contracts import json_sha256, utc_now


_SCHEMA_VERSION = 2
_DDL = """
CREATE TABLE IF NOT EXISTS records (
    record_id TEXT PRIMARY KEY,
    schema_name TEXT NOT NULL,
    asset_sha256 TEXT NOT NULL,
    asset_size INTEGER NOT NULL CHECK (asset_size >= 0),
    asset_type TEXT NOT NULL CHECK (asset_type IN ('image', 'model_3d', 'document', 'other')),
    media_type TEXT NOT NULL,
    zone TEXT NOT NULL CHECK (zone IN ('observation', 'truth')),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('physical', 'synthetic', 'fast_geo', 'unknown')),
    source_ref TEXT,
    authorization_status TEXT NOT NULL CHECK (authorization_status IN ('unknown', 'pending', 'approved', 'restricted', 'rejected')),
    allowed_uses_json TEXT NOT NULL,
    rights_evidence_ref TEXT,
    physical_qualification TEXT NOT NULL CHECK (physical_qualification IN ('unknown', 'not_applicable', 'pending', 'supported', 'unsupported')),
    physical_evidence_ref TEXT,
    training_eligibility TEXT NOT NULL CHECK (training_eligibility IN ('unknown', 'pending', 'eligible', 'ineligible')),
    training_evidence_ref TEXT,
    physics_claim INTEGER NOT NULL CHECK (physics_claim IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS records_zone_idx ON records(zone);
CREATE INDEX IF NOT EXISTS records_asset_hash_idx ON records(asset_sha256);

CREATE TABLE IF NOT EXISTS validation_receipts (
    validation_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL REFERENCES records(record_id),
    purpose TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('PASS', 'FAIL', 'BLOCKED')),
    receipt_json TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS validation_record_idx ON validation_receipts(record_id, created_at);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    schema_name TEXT NOT NULL,
    zone TEXT NOT NULL CHECK (zone IN ('observation', 'truth')),
    purpose TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshot_members (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    member_id TEXT NOT NULL,
    record_id TEXT NOT NULL REFERENCES records(record_id),
    asset_sha256 TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, member_id),
    UNIQUE (snapshot_id, record_id)
);
CREATE INDEX IF NOT EXISTS snapshot_member_record_idx ON snapshot_members(record_id);

CREATE TABLE IF NOT EXISTS evaluation_joins (
    join_id TEXT PRIMARY KEY,
    observation_snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    truth_snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    evidence_ref TEXT NOT NULL,
    authorized_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relation_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_group_id TEXT NOT NULL,
    pair_key TEXT NOT NULL,
    left_record_id TEXT NOT NULL REFERENCES records(record_id),
    right_record_id TEXT NOT NULL REFERENCES records(record_id),
    relation_status TEXT NOT NULL CHECK (relation_status IN ('R0', 'R1', 'R2', 'TINY_CONTACT', 'UNKNOWN')),
    decision TEXT NOT NULL CHECK (decision IN ('proposed', 'accepted', 'rejected', 'revoked', 'needs_review')),
    evidence_refs_json TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS relation_pair_idx ON relation_events(pair_key, sequence);

CREATE TABLE IF NOT EXISTS search_indexes (
    index_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    encoder_id TEXT NOT NULL,
    dimension INTEGER NOT NULL CHECK (dimension > 0),
    index_sha256 TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS search_index_lookup_idx
    ON search_indexes(snapshot_id, encoder_id, created_at);

CREATE TABLE IF NOT EXISTS search_vectors (
    index_id TEXT NOT NULL REFERENCES search_indexes(index_id),
    snapshot_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    dimension INTEGER NOT NULL CHECK (dimension > 0),
    vector_json TEXT NOT NULL,
    vector_sha256 TEXT NOT NULL,
    PRIMARY KEY (index_id, member_id),
    FOREIGN KEY (snapshot_id, member_id)
        REFERENCES snapshot_members(snapshot_id, member_id)
);

CREATE TABLE IF NOT EXISTS acceptance_receipts (
    receipt_id TEXT PRIMARY KEY,
    receipt_json TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    sequence INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    actor_name TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    details_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE
);
"""


class Database:
    """Creates managed local directories and a versioned SQLite database."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).expanduser().absolute()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path = self.root / "metadata.sqlite3"
        self.snapshot_root = self.root / "snapshots"
        self.receipt_root = self.root / "receipts"
        managed_dirs = (
            self.root,
            self.root / "assets",
            self.root / "assets" / "observation",
            self.root / "assets" / "truth",
            self.snapshot_root,
            self.receipt_root,
        )
        for path in managed_dirs:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            if os.name == "posix":
                path.chmod(0o700)
        self.asset_stores = {
            "observation": LocalAssetStore(self.root / "assets" / "observation"),
            "truth": LocalAssetStore(self.root / "assets" / "truth"),
        }
        self._initialize()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(f"BEGIN IMMEDIATE;\n{_DDL}")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, _SCHEMA_VERSION):
                raise RuntimeError(
                    f"database schema version {version} is not supported; expected {_SCHEMA_VERSION}"
                )
            if version == 1:
                self._migrate_search_index_v1(connection)
            connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        if os.name == "posix" and self.db_path.exists():
            self.db_path.chmod(0o600)

    @staticmethod
    def _migrate_search_index_v1(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(search_vectors)").fetchall()
        }
        if "index_id" in columns:
            return
        connection.execute("ALTER TABLE search_vectors RENAME TO search_vectors_v1")
        connection.execute(
            """CREATE TABLE search_vectors (
                index_id TEXT NOT NULL REFERENCES search_indexes(index_id),
                snapshot_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                dimension INTEGER NOT NULL CHECK (dimension > 0),
                vector_json TEXT NOT NULL,
                vector_sha256 TEXT NOT NULL,
                PRIMARY KEY (index_id, member_id),
                FOREIGN KEY (snapshot_id, member_id)
                    REFERENCES snapshot_members(snapshot_id, member_id)
            )"""
        )
        groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
        for row in connection.execute(
            "SELECT * FROM search_vectors_v1 ORDER BY snapshot_id, encoder_id, member_id"
        ).fetchall():
            groups.setdefault((row["snapshot_id"], row["encoder_id"]), []).append(row)
        for (snapshot_id, encoder_id), rows in groups.items():
            index_id = str(uuid.uuid4())
            vectors = {row["member_id"]: row["vector_json"] for row in rows}
            vector_hash_input = {
                member_id: json.loads(vector_json)
                for member_id, vector_json in vectors.items()
            }
            index_hash = json_sha256(
                {
                    "snapshot_id": snapshot_id,
                    "encoder_id": encoder_id,
                    "dimension": rows[0]["dimension"],
                    "vectors": vector_hash_input,
                }
            )
            created_at = utc_now()
            connection.execute(
                """INSERT INTO search_indexes
                   (index_id, snapshot_id, encoder_id, dimension, index_sha256,
                    created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    index_id,
                    snapshot_id,
                    encoder_id,
                    rows[0]["dimension"],
                    index_hash,
                    "system-migration",
                    created_at,
                ),
            )
            for row in rows:
                connection.execute(
                    """INSERT INTO search_vectors
                       (index_id, snapshot_id, member_id, dimension, vector_json, vector_sha256)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        index_id,
                        snapshot_id,
                        row["member_id"],
                        row["dimension"],
                        row["vector_json"],
                        row["vector_sha256"],
                    ),
                )
        connection.execute("DROP TABLE search_vectors_v1")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def asset_store(self, zone: str) -> LocalAssetStore:
        try:
            return self.asset_stores[zone]
        except KeyError as exc:
            raise ValueError(f"unknown data zone: {zone}") from exc

