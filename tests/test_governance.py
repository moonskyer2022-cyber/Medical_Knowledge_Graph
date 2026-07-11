import pandas as pd

from api.safety import assess_question, load_safety_policy, safety_response
from api.source_registry import get_source, load_source_registry, validate_source_titles
from scripts.clean import validate_source_provenance


def test_safety_policy_has_versioned_rules_and_default():
    policy = load_safety_policy()
    assert policy["version"]
    assert policy["default"]["action"] == "allowed"
    assert any(rule["action"] == "blocked" for rule in policy["rules"])


def test_safety_response_uses_policy_disclaimer():
    response = safety_response(assess_question("普通药品信息查询"))
    assert response["action"] == "allowed"
    assert "不能替代" in response["disclaimer"]


def test_source_registry_resolves_known_guideline_and_rejects_unknown_title():
    registry = load_source_registry()
    source = get_source("中国高血压防治指南")
    assert len(registry) >= 7
    assert source and source["source_id"] == "SRC-001"
    assert source["verification_status"] == "metadata_verified"
    assert validate_source_titles({"中国高血压防治指南", "未登记来源"}) == ["未登记来源"]


def test_cleaning_rejects_unregistered_source_references():
    relations = pd.DataFrame({"source": ["中国高血压防治指南", "未登记来源"]})
    plans = pd.DataFrame({"source": ["中国2型糖尿病防治指南"]})
    assert validate_source_provenance(relations, plans) == ["unregistered source: 未登记来源"]
