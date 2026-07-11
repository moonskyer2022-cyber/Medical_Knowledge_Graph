"""Read-only source registry used by Graph-RAG citations and data validation."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "data" / "source_registry.csv"
REQUIRED_COLUMNS = {"source_id", "title", "publisher", "document_type", "version", "published_at", "url", "accessed_at", "verification_status", "notes"}


@lru_cache(maxsize=1)
def load_source_registry() -> dict[str, dict[str, str]]:
    """Return source records keyed by the title used in graph data."""
    with REGISTRY_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError(f"invalid source registry columns: {REGISTRY_PATH}")
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    titles = [row["title"] for row in rows]
    if "" in titles or len(rows) == 0:
        raise ValueError("source registry must contain non-empty titles")
    if len(set(titles)) != len(titles):
        raise ValueError("source registry contains duplicate titles")
    return {row["title"]: row for row in rows}


def get_source(title: str) -> dict[str, str] | None:
    return load_source_registry().get(title.strip())


def validate_source_titles(titles: set[str]) -> list[str]:
    registry = load_source_registry()
    return sorted(title for title in titles if title and title not in registry)
