"""Command-line access to the local test-stage workflow."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys
from typing import Any

from .contracts import Clearance, IntakeMetadata
from .security import Actor
from .workflow import BrokyData


_DEMO_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jK9sAAAAASUVORK5CYII="
)


def _actor(args: argparse.Namespace) -> Actor:
    return Actor(args.actor, args.role)


def _json_print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _comma_values(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="broky-data")
    parser.add_argument(
        "--root",
        default=str(Path.home() / ".local" / "share" / "broky_data"),
        help="local application data directory",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="initialize the local database and storage")
    demo = subparsers.add_parser("demo", help="run a synthetic end-to-end workflow")
    demo.add_argument("--output-dir", default="./broky_data_demo_output")

    register = subparsers.add_parser("register", help="register an asset for review")
    _add_identity(register, default_role="registrar")
    register.add_argument("--file", required=True)
    register.add_argument("--asset-type", choices=["image", "model_3d", "document", "other"], required=True)
    register.add_argument("--media-type", default="application/octet-stream")
    register.add_argument("--zone", choices=["observation", "truth"], default="observation")
    register.add_argument("--source-kind", choices=["physical", "synthetic", "fast_geo", "unknown"], default="unknown")
    register.add_argument("--source-ref")

    clearance = subparsers.add_parser("clearance", help="record human rights and qualification decisions")
    _add_identity(clearance, default_role="curator")
    clearance.add_argument("--record-id", required=True)
    clearance.add_argument("--authorization", choices=["unknown", "pending", "approved", "restricted", "rejected"], required=True)
    clearance.add_argument("--allowed-uses", default="")
    clearance.add_argument("--rights-evidence-ref")
    clearance.add_argument("--physical-qualification", choices=["unknown", "not_applicable", "pending", "supported", "unsupported"], default="unknown")
    clearance.add_argument("--physical-evidence-ref")
    clearance.add_argument("--training-eligibility", choices=["unknown", "pending", "eligible", "ineligible"], default="unknown")
    clearance.add_argument("--training-evidence-ref")
    clearance.add_argument("--physics-claim", action="store_true")

    validate = subparsers.add_parser("validate", help="validate an asset for a specific use")
    _add_identity(validate, default_role="registrar")
    validate.add_argument("--record-id", required=True)
    validate.add_argument("--purpose", choices=["internal_review", "model_training", "evaluation", "internal_report", "public_release"], required=True)

    snapshot = subparsers.add_parser("snapshot", help="freeze a versioned dataset snapshot")
    _add_identity(snapshot, default_role="analyst")
    snapshot.add_argument("--record-id", action="append", required=True)
    snapshot.add_argument("--zone", choices=["observation", "truth"], default="observation")
    snapshot.add_argument("--purpose", choices=["internal_review", "model_training", "evaluation", "internal_report", "public_release"], required=True)

    relation = subparsers.add_parser("relation", help="record a human-reviewed relationship decision")
    _add_identity(relation, default_role="reviewer")
    relation.add_argument("--left", required=True)
    relation.add_argument("--right", required=True)
    relation.add_argument("--status", choices=["R0", "R1", "R2", "TINY_CONTACT", "UNKNOWN"], required=True)
    relation.add_argument("--decision", choices=["proposed", "accepted", "rejected", "revoked", "needs_review"], required=True)
    relation.add_argument("--evidence-ref", action="append", default=[])

    index = subparsers.add_parser("index", help="build a small exact-cosine feature index")
    _add_identity(index, default_role="analyst")
    index.add_argument("--snapshot-id", required=True)
    index.add_argument("--encoder-id", required=True)
    index.add_argument("--features-json", required=True)

    search = subparsers.add_parser("search", help="query a derived Observation index")
    _add_identity(search, default_role="analyst")
    search.add_argument("--snapshot-id", required=True)
    search.add_argument("--encoder-id", required=True)
    search.add_argument("--vector-json", required=True)
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--index-id")

    stats = subparsers.add_parser("stats", help="summarize records and quality denominators")
    _add_identity(stats, default_role="analyst")
    stats.add_argument("--zone", choices=["observation", "truth", "all"], default="observation")
    stats.add_argument("--output-dir")

    card = subparsers.add_parser("card", help="generate an internal HTML specimen card")
    _add_identity(card, default_role="analyst")
    card.add_argument("--record-id", required=True)
    card.add_argument("--output-dir", required=True)

    join = subparsers.add_parser("evaluation-join", help="authorize a Truth/Observation evaluation pairing")
    _add_identity(join, default_role="evaluator")
    join.add_argument("--observation-snapshot-id", required=True)
    join.add_argument("--truth-snapshot-id", required=True)
    join.add_argument("--evidence-ref", required=True)

    receipt = subparsers.add_parser("receipt", help="write a quality/function acceptance receipt")
    _add_identity(receipt, default_role="auditor")
    receipt.add_argument("--scope", required=True)
    receipt.add_argument("--quality-json", required=True, help="JSON file containing a list of checks")
    receipt.add_argument("--functionality-json", required=True, help="JSON file containing a list of checks")

    audit = subparsers.add_parser("audit", help="verify or export the local audit chain")
    _add_identity(audit, default_role="auditor")
    audit.add_argument("action", choices=["verify", "export"])
    audit.add_argument("--destination")
    return parser


def _add_identity(parser: argparse.ArgumentParser, default_role: str) -> None:
    parser.add_argument("--actor", default="local-operator")
    parser.add_argument("--role", default=default_role)


def _run_demo(app: BrokyData, output_dir: str) -> dict[str, object]:
    registrar = Actor("demo-registrar", "registrar")
    curator = Actor("demo-curator", "curator")
    reviewer = Actor("demo-reviewer", "reviewer")
    analyst = Actor("demo-analyst", "analyst")
    auditor = Actor("demo-auditor", "auditor")
    clearance = Clearance(
        authorization_status="approved",
        allowed_uses=("internal_review", "model_training", "internal_report"),
        rights_evidence_ref="demo-rights-record",
        physical_qualification="not_applicable",
        training_eligibility="eligible",
        training_evidence_ref="demo-training-review",
    )
    records = []
    for source_ref in ("demo-fragment-a", "demo-fragment-b"):
        record = app.registry.register_bytes(
            _DEMO_PNG,
            IntakeMetadata(
                asset_type="image",
                media_type="image/png",
                source_kind="synthetic",
                source_ref=source_ref,
            ),
            registrar,
        )
        records.append(app.registry.review_clearance(record.record_id, clearance, curator))

    validation = app.validation.validate_record(
        records[0].record_id, "internal_report", analyst
    )
    training_snapshot = app.datasets.create_snapshot(
        [record.record_id for record in records],
        "observation",
        "model_training",
        analyst,
    )
    member_ids = training_snapshot["member_ids"]
    features = {
        member_ids[0]: [1.0, 0.0, 0.0],
        member_ids[1]: [0.8, 0.2, 0.0],
    }
    index_info = app.search.build_index(
        training_snapshot["snapshot_id"], "demo-encoder-v1", features, analyst
    )
    hits = app.search.query(
        training_snapshot["snapshot_id"],
        "demo-encoder-v1",
        [1.0, 0.0, 0.0],
        analyst,
        limit=2,
    )
    relation_group = app.relations.decide_pair(
        records[0].record_id,
        records[1].record_id,
        "UNKNOWN",
        "needs_review",
        (),
        reviewer,
    )
    summary = app.analytics.summary(analyst, zone="observation")
    card = app.outputs.generate_specimen_card(
        records[0].record_id, output_dir, analyst
    )
    inventory = app.outputs.generate_inventory_report(summary, output_dir, analyst)
    receipt = app.acceptance.create_receipt(
        "synthetic-smoke-test",
        [{"check_id": "asset-validation", "status": "PASS", "evidence_ref": validation.validation_id}],
        [
            {"check_id": "search-query", "status": "PASS", "evidence_ref": index_info["index_sha256"][:32]},
            {"check_id": "html-output", "status": "PASS", "evidence_ref": card["sha256"][:32]},
        ],
        auditor,
    )
    audit_result = app.audit.verify_chain(auditor)
    return {
        "status": "PASS" if audit_result["valid"] else "FAIL",
        "record_ids": [record.record_id for record in records],
        "validation": validation.as_dict(),
        "snapshot_id": training_snapshot["snapshot_id"],
        "index": index_info,
        "search_hits": hits,
        "relation_event_group": relation_group,
        "analytics": summary,
        "outputs": [card, inventory],
        "acceptance_receipt": receipt,
        "audit": audit_result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        app = BrokyData(args.root)
        if args.command == "init":
            _json_print({"initialized": True, "root": str(app.database.root)})
        elif args.command == "demo":
            _json_print(_run_demo(app, args.output_dir))
        elif args.command == "register":
            record = app.registry.register_file(
                args.file,
                IntakeMetadata(
                    asset_type=args.asset_type,
                    media_type=args.media_type,
                    zone=args.zone,
                    source_kind=args.source_kind,
                    source_ref=args.source_ref,
                ),
                _actor(args),
            )
            _json_print(record.__dict__)
        elif args.command == "clearance":
            record = app.registry.review_clearance(
                args.record_id,
                Clearance(
                    authorization_status=args.authorization,
                    allowed_uses=_comma_values(args.allowed_uses),
                    rights_evidence_ref=args.rights_evidence_ref,
                    physical_qualification=args.physical_qualification,
                    physical_evidence_ref=args.physical_evidence_ref,
                    training_eligibility=args.training_eligibility,
                    training_evidence_ref=args.training_evidence_ref,
                    physics_claim=args.physics_claim,
                ),
                _actor(args),
            )
            _json_print(record.__dict__)
        elif args.command == "validate":
            _json_print(app.validation.validate_record(args.record_id, args.purpose, _actor(args)).as_dict())
        elif args.command == "snapshot":
            _json_print(app.datasets.create_snapshot(args.record_id, args.zone, args.purpose, _actor(args)))
        elif args.command == "relation":
            _json_print({"event_group_id": app.relations.decide_pair(args.left, args.right, args.status, args.decision, args.evidence_ref, _actor(args))})
        elif args.command == "index":
            vectors = json.loads(Path(args.features_json).read_text(encoding="utf-8"))
            _json_print(app.search.build_index(args.snapshot_id, args.encoder_id, vectors, _actor(args)))
        elif args.command == "search":
            vector = json.loads(args.vector_json)
            _json_print(app.search.query(args.snapshot_id, args.encoder_id, vector, _actor(args), args.limit, args.index_id))
        elif args.command == "stats":
            zone = None if args.zone == "all" else args.zone
            summary = app.analytics.summary(_actor(args), zone=zone)
            if args.output_dir:
                _json_print({"summary": summary, "report": app.outputs.generate_inventory_report(summary, args.output_dir, _actor(args))})
            else:
                _json_print(summary)
        elif args.command == "card":
            _json_print(app.outputs.generate_specimen_card(args.record_id, args.output_dir, _actor(args)))
        elif args.command == "evaluation-join":
            _json_print(app.datasets.create_evaluation_join(args.observation_snapshot_id, args.truth_snapshot_id, args.evidence_ref, _actor(args)))
        elif args.command == "receipt":
            quality = json.loads(Path(args.quality_json).read_text(encoding="utf-8"))
            functionality = json.loads(Path(args.functionality_json).read_text(encoding="utf-8"))
            _json_print(app.acceptance.create_receipt(args.scope, quality, functionality, _actor(args)))
        elif args.command == "audit":
            if args.action == "verify":
                _json_print(app.audit.verify_chain(_actor(args)))
            elif args.destination:
                _json_print({"path": str(app.audit.export_jsonl(args.destination, _actor(args)))})
            else:
                parser.error("audit export requires --destination")
        return 0
    except (OSError, ValueError, KeyError, PermissionError, RuntimeError) as exc:
        print(f"broky-data: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

