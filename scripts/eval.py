"""Run evaluation cases against live API."""

import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "tests" / "eval_cases.json"
BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")


def check_recommend(case: dict) -> tuple[bool, str]:
    q = case["query"]
    params = {k: v for k, v in q.items() if v}
    resp = requests.get(f"{BASE}/recommend", params=params, timeout=10)
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}: {resp.text}"

    data = resp.json()
    if case.get("expect_min_count") and data["count"] < case["expect_min_count"]:
        return False, f"count {data['count']} < {case['expect_min_count']}"

    drug_names = []
    for item in data.get("results") or []:
        for d in item.get("drugs") or []:
            drug_names.append(d.get("generic_name", ""))

    for expected in case.get("expect_drugs") or []:
        if not any(expected in n for n in drug_names):
            return False, f"missing expected drug: {expected}"

    if case.get("expect_icd"):
        icds = [r.get("icd") for r in data.get("results") or []]
        if not any(case["expect_icd"] in (i or "") for i in icds):
            return False, f"missing ICD {case['expect_icd']}"

    if case.get("expect_disease"):
        diseases = [r.get("disease") for r in data.get("results") or []]
        if not any(case["expect_disease"] in (d or "") for d in diseases):
            return False, f"missing disease {case['expect_disease']}"

    return True, f"ok ({data['count']} results)"


def check_interaction(case: dict) -> tuple[bool, str]:
    drugs = ",".join(case["drugs"])
    resp = requests.get(f"{BASE}/interactions", params={"drugs": drugs}, timeout=10)
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}"
    data = resp.json()
    if case.get("expect_interaction"):
        if not data.get("interactions"):
            return False, "expected interaction not found"
        sev = case.get("expect_severity")
        if sev and not any(i.get("severity") == sev for i in data["interactions"]):
            return False, f"expected severity {sev}"
    elif case.get("expect_safe") and not data.get("safe"):
        return False, "expected safe but conflicts found"
    return True, "ok"


def check_qa(case: dict) -> tuple[bool, str]:
    resp = requests.post(f"{BASE}/qa", json={"question": case["question"]}, timeout=10)
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}"
    data = resp.json()
    if case.get("expect_intent") and data.get("intent") != case["expect_intent"]:
        return False, f"intent {data.get('intent')} != {case['expect_intent']}"
    for kw in case.get("expect_answer_contains") or []:
        if kw not in data.get("answer", ""):
            return False, f"answer missing: {kw}"
    return True, "ok"


def main() -> int:
    if not CASES.exists():
        print(f"Cases file not found: {CASES}")
        return 1

    cases = json.loads(CASES.read_text(encoding="utf-8"))
    passed = 0
    failed = 0

    try:
        health = requests.get(f"{BASE}/health", timeout=5)
        health.raise_for_status()
    except Exception as exc:
        print(f"API not reachable at {BASE}: {exc}")
        return 1

    for i, case in enumerate(cases, 1):
        case_type = case.get("type", "recommend")
        if case_type == "recommend":
            ok, msg = check_recommend(case)
        elif case_type == "interaction":
            ok, msg = check_interaction(case)
        elif case_type == "qa":
            ok, msg = check_qa(case)
        else:
            ok, msg = False, f"unknown type: {case_type}"

        label = case.get("name") or str(case.get("query") or case.get("drugs") or case.get("question"))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] #{i} {label}: {msg}")
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\nResult: {passed} passed, {failed} failed, {len(cases)} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
