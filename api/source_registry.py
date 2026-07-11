"""Read-only source registry used by Graph-RAG citations and data validation."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from threading import Lock
from datetime import UTC, datetime
import uuid


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "data" / "source_registry.csv"
REVIEWS_PATH = ROOT / "data" / "source_reviews.csv"
_WRITE_LOCK = Lock()
REQUIRED_COLUMNS = {"source_id", "title", "publisher", "document_type", "version", "published_at", "url", "accessed_at", "verification_status", "content_review_status", "metadata_reviewed_at", "content_reviewed_at", "last_review_id", "next_review_due", "notes"}


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


def get_source_by_id(source_id: str) -> dict[str, str] | None:
    return next((source for source in load_source_registry().values() if source["source_id"] == source_id), None)


def clear_source_registry_cache() -> None:
    load_source_registry.cache_clear()


def list_source_reviews(source_id: str | None = None) -> list[dict[str, str]]:
    if not REVIEWS_PATH.exists():
        return []
    with REVIEWS_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]
    if source_id:
        rows = [row for row in rows if row.get("source_id") == source_id]
    return list(reversed(rows))


def record_source_review(source_id: str, review_type: str, reviewer_id: str, reviewer_role: str, outcome: str, evidence_url: str, notes: str, next_review_due: str = "") -> tuple[str, dict[str, str]]:
    """Persist a review decision and update the source registry for the demo workflow."""
    if review_type not in {"metadata", "clinical_content"}:
        raise ValueError("unsupported review type")
    if outcome not in {"approved", "needs_revision", "rejected"}:
        raise ValueError("unsupported review outcome")
    if outcome == "approved" and not evidence_url.startswith(("https://", "http://")):
        raise ValueError("approved reviews require an evidence URL")
    with _WRITE_LOCK:
        with REGISTRY_PATH.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
        target = next((row for row in rows if row.get("source_id") == source_id), None)
        if not target:
            raise ValueError(f"unknown source ID: {source_id}")
        now = datetime.now(UTC).date().isoformat()
        review_id = f"REV-{now.replace('-', '')}-{source_id}-{uuid.uuid4().hex[:8]}"
        if review_type == "metadata":
            target["verification_status"] = "metadata_verified" if outcome == "approved" else "metadata_needs_revision"
            target["metadata_reviewed_at"] = now
        else:
            target["content_review_status"] = "clinically_reviewed" if outcome == "approved" else "content_needs_revision"
            target["content_reviewed_at"] = now
        target["last_review_id"] = review_id
        target["next_review_due"] = next_review_due
        with REGISTRY_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        review_fields = ["review_id", "source_id", "review_type", "reviewer_id", "reviewer_role", "outcome", "evidence_url", "reviewed_at", "next_review_due", "notes"]
        REVIEWS_PATH.parent.mkdir(parents=True, exist_ok=True)
        exists = REVIEWS_PATH.exists() and REVIEWS_PATH.stat().st_size > 0
        with REVIEWS_PATH.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=review_fields)
            if not exists:
                writer.writeheader()
            writer.writerow({"review_id": review_id, "source_id": source_id, "review_type": review_type, "reviewer_id": reviewer_id, "reviewer_role": reviewer_role, "outcome": outcome, "evidence_url": evidence_url, "reviewed_at": now, "next_review_due": next_review_due, "notes": notes})
        clear_source_registry_cache()
    return review_id, target


def validate_source_titles(titles: set[str]) -> list[str]:
    registry = load_source_registry()
    return sorted(title for title in titles if title and title not in registry)
