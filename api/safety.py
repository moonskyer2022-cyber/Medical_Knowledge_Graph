"""Safety guardrails for the clinical-assistance Q&A endpoint."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "config" / "safety_policy.json"


@dataclass(frozen=True)
class SafetyDecision:
    action: str
    level: str
    reasons: list[str]
    message: str

    def as_dict(self, disclaimer: str) -> dict[str, object]:
        return {"action": self.action, "level": self.level, "reasons": self.reasons, "message": self.message, "disclaimer": disclaimer}


@lru_cache(maxsize=1)
def load_safety_policy() -> dict[str, object]:
    """Load and validate the version-controlled safety policy."""
    with POLICY_PATH.open(encoding="utf-8") as handle:
        policy = json.load(handle)
    if not isinstance(policy.get("disclaimer"), str) or not isinstance(policy.get("rules"), list):
        raise ValueError("invalid safety policy")
    if not isinstance(policy.get("default"), dict):
        raise ValueError("safety policy requires a default rule")
    for rule in policy["rules"]:
        if not all(isinstance(rule.get(key), str) for key in ("action", "level", "message")):
            raise ValueError("safety policy rule is missing required text fields")
        if not isinstance(rule.get("terms"), list) or not all(isinstance(term, str) and term for term in rule["terms"]):
            raise ValueError("safety policy rule requires non-empty terms")
    return policy


def assess_question(question: str) -> SafetyDecision:
    """Evaluate a question against the configured rules in priority order."""
    normalized = question.casefold()
    policy = load_safety_policy()
    for rule in policy["rules"]:
        hits = [term for term in rule["terms"] if term.casefold() in normalized]
        if hits:
            return SafetyDecision(rule["action"], rule["level"], hits, rule["message"])
    default = policy["default"]
    return SafetyDecision(default["action"], default["level"], [], default["message"])


def safety_response(decision: SafetyDecision) -> dict[str, object]:
    return decision.as_dict(str(load_safety_policy()["disclaimer"]))
