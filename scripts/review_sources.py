"""Record source review decisions and update source registry statuses."""

from __future__ import annotations

import argparse
import csv
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.source_registry import record_source_review

REGISTRY_PATH = ROOT / "data" / "source_registry.csv"
REVIEWS_PATH = ROOT / "data" / "source_reviews.csv"


def record_review(source_id: str, review_type: str, reviewer_id: str, reviewer_role: str, outcome: str, evidence_url: str, notes: str, next_review_due: str = "") -> str:
    review_id, _ = record_source_review(source_id, review_type, reviewer_id, reviewer_role, outcome, evidence_url, notes, next_review_due)
    return review_id
    with REGISTRY_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    target = next((row for row in rows if row["source_id"] == source_id), None)
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
    with REVIEWS_PATH.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["review_id", "source_id", "review_type", "reviewer_id", "reviewer_role", "outcome", "evidence_url", "reviewed_at", "next_review_due", "notes"])
        writer.writerow({"review_id": review_id, "source_id": source_id, "review_type": review_type, "reviewer_id": reviewer_id, "reviewer_role": reviewer_role, "outcome": outcome, "evidence_url": evidence_url, "reviewed_at": now, "next_review_due": next_review_due, "notes": notes})
    return review_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a source review decision")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--review-type", required=True, choices=("metadata", "clinical_content"))
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--reviewer-role", required=True, choices=("data_steward", "clinical_reviewer"))
    parser.add_argument("--outcome", required=True, choices=("approved", "needs_revision", "rejected"))
    parser.add_argument("--evidence-url", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--next-review-due", default="")
    args = parser.parse_args()
    print(f"Recorded source review: {record_review(**vars(args))}")


if __name__ == "__main__":
    main()
