"""API unit tests (no Neo4j required)."""

from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from api.main import app
from api.qa import answer_question


client = TestClient(app)


def test_api_root():
    resp = client.get("/api")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Pharma Knowledge Graph API"
    assert "/qa" in data["endpoints"]


@patch("api.main.driver")
def test_qa_blocks_emergency_without_querying_graph(mock_driver):
    resp = client.post("/qa", json={"question": "服药后胸痛怎么办"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "safety_blocked"
    assert data["safety"]["action"] == "blocked"
    mock_driver.session.assert_not_called()


def test_qa_unknown_intent():
    result = answer_question(
        "今天天气怎么样",
        resolve_drugs=lambda n: [],
        check_interactions=lambda ids: {},
        recommend=lambda d, i: {"count": 0, "results": []},
        drug_info=lambda n: {"results": []},
        check_contraindications=lambda ids, c: {"contraindications": []},
    )
    assert result["intent"] == "unknown"


def test_qa_interaction_intent():
    result = answer_question(
        "阿司匹林和氯吡格雷能一起吃吗？",
        resolve_drugs=lambda n: [{"id": "D001"}, {"id": "D007"}],
        check_interactions=lambda ids: {
            "interactions": [{
                "drug_a": "阿司匹林", "drug_b": "氯吡格雷",
                "severity": "moderate", "description": "出血风险",
                "recommendation": "评估出血风险",
            }],
            "duplicate_classes": [],
        },
        recommend=lambda d, i: {"count": 0, "results": []},
        drug_info=lambda n: {"results": []},
        check_contraindications=lambda ids, c: {"contraindications": []},
    )
    assert result["intent"] == "interaction_check"
    assert "氯吡格雷" in result["answer"]


@patch("api.main.driver")
def test_interactions_requires_two_drugs(mock_driver):
    resp = client.get("/interactions", params={"drugs": "阿司匹林"})
    assert resp.status_code == 400


@patch("api.main.driver")
def test_recommend_requires_query(mock_driver):
    resp = client.get("/recommend")
    assert resp.status_code == 400
