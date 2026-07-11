"""Graph-RAG response assembly with source-level provenance."""

from __future__ import annotations

from typing import Any

from api.source_registry import get_source


LOCAL_SOURCES = {
    "interaction_check": ("药物相互作用数据集", "data/clean/drug_interactions.csv"),
    "contraindication_check": ("药物禁忌数据集", "data/clean/contraindications.csv"),
    "drug_info": ("医药知识图谱", "data/clean/relations.csv"),
}


def _citation(index: int, title: str, locator: str, claim: str, source_type: str) -> dict[str, str]:
    citation = {"id": f"S{index}", "title": title or "未标注来源", "locator": locator, "claim": claim, "source_type": source_type}
    source = get_source(title) if title else None
    if source:
        citation.update({
            "source_id": source["source_id"], "publisher": source["publisher"],
            "version": source["version"], "published_at": source["published_at"],
            "url": source["url"], "verification_status": source["verification_status"],
        })
    return citation


def build_grounded_response(result: dict[str, Any]) -> dict[str, Any]:
    """Attach Cypher retrieval metadata and deduplicated citations to a QA result."""
    intent = result.get("intent", "unknown")
    data = result.get("data") or {}
    citations: list[dict[str, str]] = []
    if intent == "recommend":
        for item in data.get("results", [])[:5]:
            citations.append(_citation(len(citations) + 1, item.get("source") or "未标注指南", "Plan.source", f"{item.get('disease', '')}：{item.get('plan', '')}", "clinical_guideline"))
    elif intent == "drug_info":
        for item in data.get("results", [])[:1]:
            for disease in item.get("diseases") or []:
                if disease.get("source"):
                    citations.append(_citation(len(citations) + 1, disease["source"], "TREATS.source", f"{item.get('drug', '')} 与 {disease.get('disease', '')} 的治疗关系", "clinical_guideline"))
        if not citations:
            title, locator = LOCAL_SOURCES["drug_info"]
            citations.append(_citation(1, title, locator, "药品适应症关系", "knowledge_graph"))
    elif intent in LOCAL_SOURCES and data:
        title, locator = LOCAL_SOURCES[intent]
        citations.append(_citation(1, title, locator, "图谱检索结果", "knowledge_graph"))
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in citations:
        key = (item["title"], item["locator"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    result["retrieval"] = {"strategy": "cypher_graph_rag", "grounded": bool(unique), "context_records": sum(len(v) for v in data.values() if isinstance(v, list))}
    result["citations"] = unique
    return result
