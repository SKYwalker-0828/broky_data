"""M07 read-only aggregate reporting with explicit record denominators."""

from __future__ import annotations

from collections import Counter

from .audit import append_event
from .database import Database
from .security import Actor
from .service import Service


class AnalyticsService(Service):
    def summary(self, actor: Actor, zone: str | None = None) -> dict[str, object]:
        if zone is None:
            permission = "analytics:read_all"
        elif zone == "observation":
            permission = "analytics:read_observation"
        elif zone == "truth":
            permission = "analytics:read_all"
        else:
            raise ValueError("zone must be observation, truth, or None")
        self._authorize(actor, permission, "build_analytics_summary", "analytics", zone or "all")
        with self.database.connect() as connection:
            query = "SELECT * FROM records"
            parameters: tuple[object, ...] = ()
            if zone is not None:
                query += " WHERE zone = ?"
                parameters = (zone,)
            records = connection.execute(query, parameters).fetchall()
            record_ids = [row["record_id"] for row in records]
            if record_ids:
                placeholders = ",".join("?" for _ in record_ids)
                validation_rows = connection.execute(
                    f"""SELECT v.purpose, v.outcome, COUNT(*) AS count
                        FROM validation_receipts v
                        JOIN (
                            SELECT record_id, purpose, MAX(rowid) AS latest_rowid
                            FROM validation_receipts
                            WHERE record_id IN ({placeholders})
                            GROUP BY record_id, purpose
                        ) latest ON latest.latest_rowid = v.rowid
                        GROUP BY v.purpose, v.outcome""",
                    record_ids,
                ).fetchall()
            else:
                validation_rows = []
            snapshots = connection.execute(
                "SELECT zone, COUNT(*) AS count FROM snapshots"
                + (" WHERE zone = ?" if zone is not None else "")
                + " GROUP BY zone",
                parameters,
            ).fetchall()
            relation_rows = connection.execute(
                """WITH latest AS (
                       SELECT pair_key, MAX(sequence) AS sequence
                       FROM relation_events GROUP BY pair_key
                   ), latest_group AS (
                       SELECT r.pair_key, r.event_group_id
                       FROM relation_events r
                       JOIN latest l ON l.sequence = r.sequence
                   )
                   SELECT r.relation_status, r.decision, COUNT(*) AS count
                   FROM relation_events r
                   JOIN latest_group g
                     ON g.pair_key = r.pair_key AND g.event_group_id = r.event_group_id
                   WHERE r.left_record_id < r.right_record_id
                   GROUP BY r.relation_status, r.decision"""
            ).fetchall()
        total = len(records)
        validations_by_purpose: dict[str, dict[str, object]] = {}
        for row in validation_rows:
            purpose_summary = validations_by_purpose.setdefault(
                row["purpose"],
                {"assessed": 0, "outcomes": {}},
            )
            purpose_summary["assessed"] += row["count"]
            purpose_summary["outcomes"][row["outcome"]] = row["count"]
        for purpose_summary in validations_by_purpose.values():
            purpose_summary["not_assessed"] = total - purpose_summary["assessed"]
        result: dict[str, object] = {
            "schema": "broky_data.analytics.v1",
            "scope": zone or "all",
            "record_denominator": total,
            "record_counts": {
                "asset_type": self._counts(records, "asset_type"),
                "source_kind": self._counts(records, "source_kind"),
                "authorization_status": self._counts(records, "authorization_status"),
                "physical_qualification": self._counts(records, "physical_qualification"),
                "training_eligibility": self._counts(records, "training_eligibility"),
            },
            "validation_by_purpose": validations_by_purpose,
            "snapshot_counts_by_zone": {
                row["zone"]: row["count"] for row in snapshots
            },
            "latest_relation_pair_counts": {
                f"{row['relation_status']}:{row['decision']}": row["count"]
                for row in relation_rows
            },
        }
        with self.database.connect() as connection:
            append_event(
                connection,
                actor,
                "build_analytics_summary",
                "analytics",
                zone or "all",
                "PASS",
                {
                    "record_denominator": total,
                    "validation_purposes": sorted(validations_by_purpose),
                },
            )
        return result

    @staticmethod
    def _counts(records, key: str) -> dict[str, int]:
        counts = Counter(row[key] for row in records)
        return dict(sorted(counts.items()))

