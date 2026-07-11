"""Small dependency-free observability helpers for the demo API."""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict, deque
from threading import Lock


LOGGER = logging.getLogger("pharmakg.api")
_WINDOWS: dict[str, deque[float]] = defaultdict(deque)
_LOCK = Lock()


def rate_limit_enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def allow_request(key: str, limit: int | None = None, window_seconds: int | None = None) -> bool:
    limit = limit or int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
    window_seconds = window_seconds or int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    now = time.monotonic()
    with _LOCK:
        bucket = _WINDOWS[key]
        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


def log_request(**fields: object) -> None:
    if os.getenv("LOG_JSON", "true").strip().lower() in {"0", "false", "no"}:
        LOGGER.info("%s", fields)
        return
    LOGGER.info(json.dumps(fields, ensure_ascii=False, separators=(",", ":")))
