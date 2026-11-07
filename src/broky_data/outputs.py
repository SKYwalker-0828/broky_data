"""M08 internal HTML specimen cards and inventory reports."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile

from .asset_store import AssetRef
from .audit import append_event
from .database import Database
from .registry import record_from_connection
from .security import Actor
from .service import Service


_EMBED_MIME = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
_MAX_EMBED_BYTES = 4 * 1024 * 1024


class OutputService(Service):
    def generate_specimen_card(
        self,
        record_id: str,
        output_dir: str | Path,
        actor: Actor,
    ) -> dict[str, str]:
        self._authorize(actor, "output:internal", "generate_specimen_card", "output", record_id)
        with self.database.connect() as connection:
            record = record_from_connection(connection, record_id)
            latest = connection.execute(
                """SELECT validation_id, receipt_sha256, outcome FROM validation_receipts
                   WHERE record_id = ? AND purpose = 'internal_report'
                   ORDER BY rowid DESC LIMIT 1""",
                (record_id,),
            ).fetchone()
        if record.zone != "observation":
            raise PermissionError("specimen cards cannot expose Truth/GT records")
        if record.authorization_status != "approved" or "internal_report" not in record.allowed_uses:
            raise PermissionError("record is not approved for internal reporting")
        if latest is None or latest["outcome"] != "PASS":
            raise ValueError("record must pass M03 validation for internal_report first")

        image_markup = "<p class=\"notice\">No inline preview is available for this asset.</p>"
        if record.media_type in _EMBED_MIME and record.asset_size <= _MAX_EMBED_BYTES:
            if not self.database.asset_store(record.zone).verify(
                AssetRef(record.asset_sha256)
            ):
                raise RuntimeError("asset integrity check failed")
            with self.database.asset_store(record.zone).open(
                AssetRef(record.asset_sha256)
            ) as stream:
                raw = stream.read()
            if len(raw) != record.asset_size:
                raise RuntimeError("asset size changed after integrity check")
            encoded = base64.b64encode(raw).decode("ascii")
            image_markup = (
                f'<img class="preview" alt="Approved asset preview" '
                f'src="data:{html.escape(record.media_type, quote=True)};base64,{encoded}">'
            )
        fields = {
            "Record reference": record.record_id,
            "Asset type": record.asset_type,
            "Media type": record.media_type,
            "Source kind": record.source_kind,
            "Authorization": record.authorization_status,
            "Physical qualification": record.physical_qualification,
            "Training eligibility": record.training_eligibility,
            "Source reference": record.source_ref or "Not recorded",
            "Validation receipt": latest["validation_id"],
            "Validation receipt SHA-256": latest["receipt_sha256"],
            "Template version": "broky_data.specimen_html.v1",
        }
        rows = "".join(
            f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>"
            for label, value in fields.items()
        )
        document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>标本记录 {html.escape(record.record_id)}</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;margin:2rem auto;max-width:900px;padding:0 1rem;color:#202624}}
h1{{font-size:1.6rem}}table{{border-collapse:collapse;width:100%;margin-top:1rem}}
th,td{{text-align:left;padding:.6rem;border-bottom:1px solid #ccd4d1;overflow-wrap:anywhere}}
th{{width:35%;font-weight:600}}.preview{{display:block;max-width:100%;max-height:65vh;object-fit:contain;margin:1rem 0}}
.notice{{color:#53615c}}.scope{{border-left:4px solid #007f73;padding:.5rem .75rem;background:#f1f6f4}}
</style></head><body>
<h1>标本记录</h1>
<p class="scope">测试阶段内部成果。对外使用前须复核数据与授权。</p>
{image_markup}<table><tbody>{rows}</tbody></table>
<p>Asset SHA-256: <code>{html.escape(record.asset_sha256)}</code></p>
</body></html>"""
        directory = Path(output_dir).expanduser().absolute()
        directory.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^A-Za-z0-9-]", "", record.record_id)
        digest = hashlib.sha256(document.encode()).hexdigest()
        target = directory / f"specimen-{safe_id}-{digest[:12]}.html"
        self._write_atomic(target, document)
        with self.database.connect() as connection:
            append_event(
                connection,
                actor,
                "generate_specimen_card",
                "output",
                record_id,
                "PASS",
                {"output_sha256": digest, "template_version": "broky_data.specimen_html.v1"},
            )
        return {"path": str(target), "sha256": digest}

    def generate_inventory_report(
        self,
        summary: dict[str, object],
        output_dir: str | Path,
        actor: Actor,
    ) -> dict[str, str]:
        self._authorize(actor, "output:internal", "generate_inventory_report", "output", "inventory")
        escaped = html.escape(json.dumps(summary, ensure_ascii=False, indent=2))
        document = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>数据概览报告</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#202624}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f3;padding:1rem}}
.scope{{border-left:4px solid #007f73;padding:.5rem .75rem}}</style></head><body>
<h1>数据概览与质量摘要</h1><p class="scope">测试阶段内部报告；统计保留登记分母。</p>
<pre>{escaped}</pre></body></html>"""
        directory = Path(output_dir).expanduser().absolute()
        directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(document.encode()).hexdigest()
        target = directory / f"inventory-report-{digest[:12]}.html"
        self._write_atomic(target, document)
        with self.database.connect() as connection:
            append_event(
                connection,
                actor,
                "generate_inventory_report",
                "output",
                "inventory",
                "PASS",
                {"output_sha256": digest},
            )
        return {"path": str(target), "sha256": digest}

    @staticmethod
    def _write_atomic(target: Path, document: str) -> None:
        fd, temporary = tempfile.mkstemp(prefix="output-", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(document)
                stream.flush()
                os.fsync(stream.fileno())
            Path(temporary).replace(target)
        finally:
            Path(temporary).unlink(missing_ok=True)

