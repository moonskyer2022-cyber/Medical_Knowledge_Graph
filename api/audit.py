"""Append-only, privacy-minimising API audit events."""

from __future__ import annotations

import json
import os
import threading
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
_LOCK = threading.Lock()
AUDIT_FIELDS = {"request_id", "user", "roles", "action", "method", "status_code", "duration_ms"}


def audit_enabled() -> bool:
    return os.getenv("AUDIT_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def audit_log_path() -> Path:
    configured = os.getenv("AUDIT_LOG_PATH", "")
    return Path(configured) if configured else ROOT / "data" / "audit" / "events.jsonl"


def append_audit_event(event: dict[str, Any]) -> None:
    """Persist an event without request parameters or clinical content."""
    if not audit_enabled():
        return
    record = {"timestamp": datetime.now(UTC).isoformat()}
    record.update({key: event[key] for key in AUDIT_FIELDS if key in event})
    target = audit_log_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, target.open("a", encoding="utf-8") as handle:
        max_bytes = int(os.getenv("AUDIT_MAX_BYTES", "10485760"))
        if target.exists() and target.stat().st_size >= max_bytes:
            backup = target.with_suffix(target.suffix + ".1")
            shutil.copyfile(target, backup)
            target.write_text("", encoding="utf-8")
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def recent_audit_events(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    target = audit_log_path()
    if not target.exists():
        return []
    lines = [line for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = lines[max(0, len(lines) - offset - limit):len(lines) - offset if offset else None]
    return [json.loads(line) for line in reversed(selected)]
