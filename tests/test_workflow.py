import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest

from broky_data import (
    Actor,
    BrokyData,
    Clearance,
    IntakeMetadata,
    PermissionDenied,
    SnapshotRejected,
)
from broky_data.cli import _run_demo


def _create_legacy_search_store(root: Path, vector_json: str) -> None:
    app = BrokyData(root)
    timestamp = "2026-11-07T00:00:00Z"
    record_id = "record-legacy"
    snapshot_id = "snapshot-legacy"
    member_id = "member-legacy"
    with app.database.connect() as connection:
        connection.execute("DROP TABLE search_vectors")
        connection.execute("DROP TABLE search_indexes")
        connection.execute(
            """CREATE TABLE search_vectors (
                snapshot_id TEXT NOT NULL,
                encoder_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                vector_json TEXT NOT NULL,
                vector_sha256 TEXT NOT NULL,
                PRIMARY KEY (snapshot_id, encoder_id, member_id)
            )"""
        )
        connection.execute(
            """INSERT INTO records (
                record_id, schema_name, asset_sha256, asset_size, asset_type,
                media_type, zone, source_kind, source_ref, authorization_status,
                allowed_uses_json, rights_evidence_ref, physical_qualification,
                physical_evidence_ref, training_eligibility, training_evidence_ref,
                physics_claim, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record_id,
                "broky_data.record.v1",
                "a" * 64,
                3,
                "image",
                "image/png",
                "observation",
                "synthetic",
                "source-legacy",
                "approved",
                '["evaluation"]',
                "rights-legacy",
                "not_applicable",
                None,
                "eligible",
                "training-legacy",
                0,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """INSERT INTO snapshots (
                snapshot_id, schema_name, zone, purpose, manifest_json,
                manifest_sha256, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot_id,
                "broky_data.snapshot.v1",
                "observation",
                "evaluation",
                "{}",
                "manifest-hash",
                "migration-test",
                timestamp,
            ),
        )
        connection.execute(
            """INSERT INTO snapshot_members
               (snapshot_id, member_id, record_id, asset_sha256)
               VALUES (?, ?, ?, ?)""",
            (snapshot_id, member_id, record_id, "a" * 64),
        )
        connection.execute(
            """INSERT INTO search_vectors
               (snapshot_id, encoder_id, member_id, dimension, vector_json, vector_sha256)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (snapshot_id, "legacy-encoder", member_id, 2, vector_json, "vector-hash"),
        )
        connection.execute("PRAGMA user_version = 1")


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.app = BrokyData(self.root / "store")
        self.registrar = Actor("registrar-test", "registrar")
        self.curator = Actor("curator-test", "curator")
        self.reviewer = Actor("reviewer-test", "reviewer")
        self.analyst = Actor("analyst-test", "analyst")
        self.evaluator = Actor("evaluator-test", "evaluator")
        self.auditor = Actor("auditor-test", "auditor")

    def register_observation(self, source_ref: str) -> str:
        record = self.app.registry.register_bytes(
            f"synthetic-{source_ref}".encode(),
            IntakeMetadata(
                asset_type="image",
                media_type="image/png",
                source_kind="synthetic",
                source_ref=source_ref,
            ),
            self.registrar,
        )
        approved = Clearance(
            authorization_status="approved",
            allowed_uses=(
                "internal_review",
                "model_training",
                "evaluation",
                "internal_report",
            ),
            rights_evidence_ref=f"rights-{source_ref}",
            physical_qualification="not_applicable",
            training_eligibility="eligible",
            training_evidence_ref=f"training-{source_ref}",
        )
        self.app.registry.review_clearance(record.record_id, approved, self.curator)
        return record.record_id

    def test_unreviewed_input_is_blocked_and_not_snapshotted(self) -> None:
        record = self.app.registry.register_bytes(
            b"unreviewed",
            IntakeMetadata(asset_type="other", source_kind="unknown"),
            self.registrar,
        )

        receipt = self.app.validation.validate_record(
            record.record_id, "internal_review", self.registrar
        )
        self.assertEqual(receipt.outcome, "BLOCKED")
        self.assertIn(
            "BLOCKED",
            {check["status"] for check in receipt.checks},
        )
        with self.assertRaises(SnapshotRejected):
            self.app.datasets.create_snapshot(
                [record.record_id], "observation", "internal_review", self.analyst
            )

    def test_empty_asset_fails_structural_validation(self) -> None:
        record = self.app.registry.register_bytes(
            b"", IntakeMetadata(asset_type="other"), self.registrar
        )
        receipt = self.app.validation.validate_record(
            record.record_id, "internal_review", self.registrar
        )
        self.assertEqual(receipt.outcome, "FAIL")
        self.assertIn(
            "asset_size",
            {check["code"] for check in receipt.checks if check["status"] == "FAIL"},
        )

    @unittest.skipUnless(os.name == "posix", "POSIX file permissions required")
    def test_managed_truth_storage_is_private_to_the_local_account(self) -> None:
        record = self.app.registry.register_bytes(
            b"private",
            IntakeMetadata(asset_type="document", zone="truth"),
            self.evaluator,
        )
        paths = [
            self.root / "store" / "assets" / "truth",
            self.root / "store" / "assets" / "truth" / "sha256",
            self.root / "store" / "assets" / "observation",
        ]
        for path in paths:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        self.assertEqual(
            stat.S_IMODE((self.root / "store" / "metadata.sqlite3").stat().st_mode),
            0o600,
        )
        asset_path = (
            self.root
            / "store"
            / "assets"
            / "truth"
            / "sha256"
            / record.asset_sha256[:2]
            / record.asset_sha256[2:]
        )
        self.assertEqual(stat.S_IMODE(asset_path.stat().st_mode), 0o600)

    def test_clearance_requires_evidence_and_fast_geo_cannot_claim_physics(self) -> None:
        record = self.app.registry.register_bytes(
            b"fast geometry",
            IntakeMetadata(asset_type="model_3d", source_kind="fast_geo"),
            self.registrar,
        )
        invalid = Clearance(
            authorization_status="approved",
            allowed_uses=("internal_review",),
            rights_evidence_ref="rights-fast-geo",
            physics_claim=True,
        )
        with self.assertRaisesRegex(ValueError, "fast_geo"):
            self.app.registry.review_clearance(record.record_id, invalid, self.curator)
        self.assertEqual(
            self.app.registry.get_record(record.record_id, self.registrar).authorization_status,
            "unknown",
        )

    def test_observation_snapshot_search_and_model_read(self) -> None:
        first = self.register_observation("fragment-a")
        second = self.register_observation("fragment-b")
        snapshot = self.app.datasets.create_snapshot(
            [first, second], "observation", "model_training", self.analyst
        )
        self.assertEqual(snapshot["schema"], "broky_data.snapshot.v1")
        manifest = json.loads(Path(snapshot["manifest_path"]).read_text(encoding="utf-8"))
        self.assertEqual(set(manifest), {
            "schema", "schema_version", "snapshot_id", "zone", "purpose", "created_at", "member_ids"
        })
        self.assertNotIn(first, manifest["member_ids"])

        vectors = {
            snapshot["member_ids"][0]: [1.0, 0.0],
            snapshot["member_ids"][1]: [0.0, 1.0],
        }
        index = self.app.search.build_index(
            snapshot["snapshot_id"], "encoder-v1", vectors, self.analyst
        )
        newer_index = self.app.search.build_index(
            snapshot["snapshot_id"],
            "encoder-v1",
            {
                snapshot["member_ids"][0]: [0.0, 1.0],
                snapshot["member_ids"][1]: [1.0, 0.0],
            },
            self.analyst,
        )
        hits = self.app.search.query(
            snapshot["snapshot_id"], "encoder-v1", [0.9, 0.1], Actor("model", "model")
        )
        self.assertEqual(index["member_count"], 2)
        self.assertNotEqual(index["index_id"], newer_index["index_id"])
        self.assertEqual(hits[0]["member_id"], snapshot["member_ids"][1])
        historical_hits = self.app.search.query(
            snapshot["snapshot_id"],
            "encoder-v1",
            [0.9, 0.1],
            Actor("model", "model"),
            index_id=index["index_id"],
        )
        self.assertEqual(historical_hits[0]["member_id"], snapshot["member_ids"][0])
        self.assertEqual(
            self.app.datasets.read_member_bytes(
                snapshot["snapshot_id"], snapshot["member_ids"][0], Actor("model", "model")
            ),
            b"synthetic-fragment-a",
        )

    def test_search_rejects_malformed_vectors_and_truth_inputs(self) -> None:
        record_id = self.register_observation("vector-record")
        snapshot = self.app.datasets.create_snapshot(
            [record_id], "observation", "model_training", self.analyst
        )
        member_id = snapshot["member_ids"][0]
        with self.assertRaisesRegex(ValueError, "finite"):
            self.app.search.build_index(
                snapshot["snapshot_id"], "encoder-v1", {member_id: [float("nan")]}, self.analyst
            )
        with self.assertRaisesRegex(ValueError, "zero"):
            self.app.search.build_index(
                snapshot["snapshot_id"], "encoder-v1", {member_id: [0.0]}, self.analyst
            )
        normalized = self.app.search._normalize([1e308, 1e308])
        self.assertAlmostEqual(sum(value * value for value in normalized), 1.0)

    def test_truth_is_separately_stored_and_denied_to_model(self) -> None:
        truth = self.app.registry.register_bytes(
            b"truth-only-payload",
            IntakeMetadata(
                asset_type="document",
                zone="truth",
                source_kind="synthetic",
                source_ref="truth-doc",
            ),
            self.evaluator,
        )
        self.app.registry.review_clearance(
            truth.record_id,
            Clearance(
                authorization_status="approved",
                allowed_uses=("evaluation",),
                rights_evidence_ref="truth-rights",
                physical_qualification="not_applicable",
            ),
            self.curator,
        )
        truth_snapshot = self.app.datasets.create_snapshot(
            [truth.record_id], "truth", "evaluation", self.evaluator
        )
        self.assertTrue(
            (self.root / "store" / "assets" / "truth" / "sha256").exists()
        )
        with self.assertRaises(PermissionDenied):
            self.app.datasets.get_snapshot(truth_snapshot["snapshot_id"], Actor("model", "model"))
        with self.assertRaises(PermissionDenied):
            self.app.datasets.read_member_bytes(
                truth_snapshot["snapshot_id"],
                truth_snapshot["member_ids"][0],
                Actor("model", "model"),
            )
        with self.assertRaises(PermissionDenied):
            self.app.validation.validate_record(
                truth.record_id, "evaluation", self.registrar
            )
        analyst_summary = self.app.analytics.summary(self.analyst, zone="observation")
        self.assertNotIn("truth", analyst_summary["snapshot_counts_by_zone"])
        self.assertEqual(
            self.app.datasets.read_member_bytes(
                truth_snapshot["snapshot_id"],
                truth_snapshot["member_ids"][0],
                self.evaluator,
            ),
            b"truth-only-payload",
        )

    def test_evaluation_join_requires_separate_evaluation_snapshots(self) -> None:
        observation_id = self.register_observation("eval-observation")
        observation_snapshot = self.app.datasets.create_snapshot(
            [observation_id], "observation", "evaluation", self.evaluator
        )
        truth_record = self.app.registry.register_bytes(
            b"eval-ground-truth",
            IntakeMetadata(asset_type="document", zone="truth", source_kind="synthetic"),
            self.evaluator,
        )
        self.app.registry.review_clearance(
            truth_record.record_id,
            Clearance(
                authorization_status="approved",
                allowed_uses=("evaluation",),
                rights_evidence_ref="eval-rights",
            ),
            self.curator,
        )
        truth_snapshot = self.app.datasets.create_snapshot(
            [truth_record.record_id], "truth", "evaluation", self.evaluator
        )
        join = self.app.datasets.create_evaluation_join(
            observation_snapshot["snapshot_id"],
            truth_snapshot["snapshot_id"],
            "approved-evaluation-run",
            self.evaluator,
        )
        self.assertTrue(join["join_id"])

    def test_relationship_history_is_mirrored_and_not_transitive(self) -> None:
        first, second, third = (
            self.register_observation(name) for name in ("rel-a", "rel-b", "rel-c")
        )
        self.app.relations.decide_pair(
            first, second, "R2", "accepted", ["evidence-ab"], self.reviewer
        )
        self.app.relations.decide_pair(
            second, third, "R2", "accepted", ["evidence-bc"], self.reviewer
        )
        history = self.app.relations.history_for_pair(first, second, self.reviewer)
        self.assertEqual(len(history), 2)
        self.assertEqual(
            {(item["left_record_id"], item["right_record_id"]) for item in history},
            {(first, second), (second, first)},
        )
        self.assertEqual(
            self.app.relations.history_for_pair(first, third, self.reviewer), []
        )
        summary = self.app.analytics.summary(self.analyst, zone="observation")
        self.assertEqual(summary["latest_relation_pair_counts"]["R2:accepted"], 2)
        with self.assertRaises(ValueError):
            self.app.relations.decide_pair(
                first, third, "R2", "accepted", [], self.reviewer
            )

    def test_specimen_card_is_internal_and_escapes_content(self) -> None:
        record_id = self.register_observation("card-record")
        self.app.validation.validate_record(record_id, "internal_report", self.analyst)
        result = self.app.outputs.generate_specimen_card(
            record_id, self.root / "reports", self.analyst
        )
        document = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("data:image/png;base64,", document)
        self.assertIn("测试阶段内部成果", document)
        with self.assertRaises(PermissionDenied):
            self.app.outputs.generate_specimen_card(
                record_id, self.root / "denied", Actor("model", "model")
            )

    def test_acceptance_receipt_preserves_blocked_state(self) -> None:
        receipt = self.app.acceptance.create_receipt(
            "test-scope",
            [{"check_id": "quality-schema", "status": "BLOCKED"}],
            [{"check_id": "workflow-test", "status": "PASS", "evidence_ref": "test-log-01"}],
            self.auditor,
        )
        self.assertEqual(receipt["quality"]["result"], "BLOCKED")
        self.assertEqual(receipt["overall_result"], "BLOCKED")
        saved = json.loads(Path(receipt["path"]).read_text(encoding="utf-8"))
        self.assertEqual(saved["overall_result"], "BLOCKED")

    def test_audit_chain_detects_tampering(self) -> None:
        self.register_observation("audit-record")
        self.assertTrue(self.app.audit.verify_chain(self.auditor)["valid"])
        with self.app.database.connect() as connection:
            connection.execute(
                "UPDATE audit_events SET details_json = '{}' WHERE sequence = 1"
            )
        result = self.app.audit.verify_chain(self.auditor)
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "event_hash_mismatch")

    def test_database_migrates_and_preserves_legacy_search_vectors(self) -> None:
        root = self.root / "legacy-store"
        root.mkdir()
        _create_legacy_search_store(root, "[1.0, 0.0]")

        migrated = BrokyData(root)
        with migrated.database.connect() as connection:
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(search_vectors)")
            }
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            vector_count = connection.execute(
                "SELECT COUNT(*) FROM search_vectors"
            ).fetchone()[0]
        self.assertIn("index_id", columns)
        self.assertEqual(version, 2)
        self.assertEqual(vector_count, 1)
        results = migrated.search.query(
            "snapshot-legacy",
            "legacy-encoder",
            [1.0, 0.0],
            Actor("migration-test", "analyst"),
        )
        self.assertEqual(results, [{"member_id": "member-legacy", "score": 1.0}])

    def test_database_migration_failure_rolls_back_schema_and_data(self) -> None:
        root = self.root / "broken-legacy-store"
        root.mkdir()
        _create_legacy_search_store(root, "not-json")

        with self.assertRaises(json.JSONDecodeError):
            BrokyData(root)

        with sqlite3.connect(root / "metadata.sqlite3") as connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(search_vectors)")
            }
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            vector_count = connection.execute(
                "SELECT COUNT(*) FROM search_vectors"
            ).fetchone()[0]
            legacy_table_count = connection.execute(
                """SELECT COUNT(*) FROM sqlite_master
                   WHERE type = 'table' AND name = 'search_vectors_v1'"""
            ).fetchone()[0]
        self.assertNotIn("index_id", columns)
        self.assertEqual(version, 1)
        self.assertEqual(vector_count, 1)
        self.assertEqual(legacy_table_count, 0)

    def test_synthetic_demo_runs_all_modules(self) -> None:
        result = _run_demo(self.app, str(self.root / "demo-output"))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["acceptance_receipt"]["overall_result"], "PASS")
        self.assertTrue(result["audit"]["valid"])
        for output in result["outputs"]:
            self.assertTrue(Path(output["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
