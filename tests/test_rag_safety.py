from api.rag import build_grounded_response
from api.safety import assess_question


def test_emergency_question_is_blocked():
    decision = assess_question("服药后胸痛和呼吸困难怎么办")
    assert decision.action == "blocked"
    assert decision.level == "critical"


def test_dose_question_requires_professional_review():
    decision = assess_question("二甲双胍剂量需要加量吗")
    assert decision.action == "review_required"
    assert "剂量" in decision.reasons


def test_recommendation_has_guideline_citation():
    response = build_grounded_response({
        "intent": "recommend",
        "data": {"results": [{"disease": "高血压", "plan": "一线方案", "source": "中国高血压防治指南"}]},
    })
    assert response["retrieval"]["strategy"] == "cypher_graph_rag"
    assert response["citations"] == [{
        "id": "S1", "title": "中国高血压防治指南", "locator": "Plan.source",
        "claim": "高血压：一线方案", "source_type": "clinical_guideline",
    }]
