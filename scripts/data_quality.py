"""Generate a lightweight data quality report without modifying source data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"


def main() -> int:
    report: dict[str, object] = {"files": {}, "errors": []}
    for path in sorted(RAW.glob("*.csv")):
        try:
            frame = pd.read_csv(path, dtype=str).fillna("")
            report["files"][path.name] = {"rows": len(frame), "columns": list(frame.columns), "empty_cells": int(frame.isna().sum().sum())}
            if frame.empty:
                report["errors"].append(f"empty dataset: {path.name}")
        except Exception as exc:
            report["errors"].append(f"cannot read {path.name}: {exc}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
