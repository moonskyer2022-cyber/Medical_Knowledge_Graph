"""Pharma knowledge graph recommendation API."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

from api import cypher as cq
from api.graph_builder import build_disease_graph, build_drug_graph
from api.qa import answer_question
from api.rag import build_grounded_response
from api.safety import assess_question

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
load_dotenv(ROOT / ".env")

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    driver.close()


app = FastAPI(
    title="Pharma KG API",
    version="1.0.0",
    description="医药知识图谱 — 推荐、相互作用、禁忌、智能问答",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if WEB.exists():
    app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


class InteractionRequest(BaseModel):
    drug_names: list[str] = Field(..., min_length=2, description="至少两种药品名称")


class ComorbidityRequest(BaseModel):
    diseases: list[str] = Field(..., min_length=1, description="疾病名称列表")


class QARequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)


def resolve_drug_ids(session, names: list[str]) -> list[str]:
    ids: list[str] = []
    for name in names:
        rows = session.run(cq.RESOLVE_DRUG, name=name.strip()).data()
        ids.extend(r["id"] for r in rows)
    return list(dict.fromkeys(ids))


@app.get("/")
def index() -> FileResponse:
    page = WEB / "index.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(page)


@app.get("/api")
def api_root() -> dict:
    return {
        "name": "Pharma Knowledge Graph API",
        "version": "1.0.0",
        "endpoints": [
            "/health", "/stats", "/recommend", "/drug", "/graph",
            "/diseases", "/drugs", "/interactions/check", "/interactions",
            "/contraindications", "/comorbidity", "/path", "/qa",
        ],
        "disclaimer": "本系统仅供辅助参考，不能替代专业医疗决策。",
    }


@app.get("/health")
def health() -> dict:
    try:
        driver.verify_connectivity()
        return {"status": "ok", "neo4j": URI}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/stats")
def stats() -> dict:
    with driver.session() as session:
        record = session.run(cq.STATS_CYPHER).single()
    return dict(record)


@app.get("/recommend")
def recommend(disease: str = Query(""), icd: str = Query("")) -> dict:
    if not disease and not icd:
        raise HTTPException(status_code=400, detail="Provide disease or icd")
    with driver.session() as session:
        results = session.run(cq.RECOMMEND_CYPHER, keyword=disease, icd=icd).data()
    return {"query": {"disease": disease, "icd": icd}, "count": len(results), "results": results}


@app.get("/drug")
def drug_info(drug_name: str = Query(...)) -> dict:
    with driver.session() as session:
        results = session.run(cq.DRUG_CYPHER, drug_name=drug_name).data()
    if not results:
        raise HTTPException(status_code=404, detail=f"Drug not found: {drug_name}")
    cleaned = []
    for row in results:
        row["adverse_effects"] = [x for x in row.get("adverse_effects") or [] if x.get("effect")]
        row["contraindications"] = [x for x in row.get("contraindications") or [] if x.get("condition")]
        row["diseases"] = [x for x in row.get("diseases") or [] if x.get("disease")]
        cleaned.append(row)
    return {"count": len(cleaned), "results": cleaned}


@app.get("/diseases")
def list_diseases() -> dict:
    with driver.session() as session:
        results = session.run(cq.LIST_DISEASES_CYPHER).data()
    return {"count": len(results), "results": results}


@app.get("/drugs")
def list_drugs() -> dict:
    with driver.session() as session:
        results = session.run(cq.LIST_DRUGS_CYPHER).data()
    return {"count": len(results), "results": results}


@app.get("/graph")
def graph(
    disease: str = Query(""),
    icd: str = Query(""),
    drug_name: str = Query(""),
) -> dict:
    if not disease and not icd and not drug_name:
        raise HTTPException(status_code=400, detail="Provide disease, icd, or drug_name")

    with driver.session() as session:
        if drug_name:
            records = session.run(cq.DRUG_GRAPH_CYPHER, drug_name=drug_name).data()
            if not records:
                return {"nodes": [], "edges": []}
            return build_drug_graph(records[0])

        record = session.run(cq.DISEASE_GRAPH_CYPHER, keyword=disease, icd=icd).single()
        if not record or not record.get("disease_id"):
            return {"nodes": [], "edges": []}
        return build_disease_graph(dict(record))


@app.post("/interactions/check")
def check_interactions_post(body: InteractionRequest) -> dict:
    return _check_interactions(body.drug_names)


@app.get("/interactions")
def check_interactions_get(drugs: str = Query(..., description="逗号分隔的药品名称")) -> dict:
    names = [d.strip() for d in drugs.split(",") if d.strip()]
    if len(names) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 drug names separated by comma")
    return _check_interactions(names)


def _check_interactions(drug_names: list[str]) -> dict:
    with driver.session() as session:
        drug_ids = resolve_drug_ids(session, drug_names)
        if len(drug_ids) < 2:
            return {
                "drug_names": drug_names,
                "resolved_count": len(drug_ids),
                "interactions": [],
                "duplicate_classes": [],
                "warnings": ["未能解析足够的药品，请检查名称或使用通用名/商品名"],
            }
        interactions = [
            r for r in session.run(cq.INTERACTION_CHECK_CYPHER, drug_ids=drug_ids).data()
            if r.get("severity")
        ]
        duplicates = session.run(cq.DUPLICATE_CLASS_CYPHER, drug_ids=drug_ids).data()
    return {
        "drug_names": drug_names,
        "resolved_count": len(drug_ids),
        "interactions": interactions,
        "duplicate_classes": duplicates,
        "safe": len(interactions) == 0 and len(duplicates) == 0,
    }


@app.get("/contraindications")
def contraindications(
    drug_name: str = Query(""),
    condition: str = Query(""),
) -> dict:
    with driver.session() as session:
        drug_ids = resolve_drug_ids(session, [drug_name]) if drug_name else []
        if drug_name and not drug_ids:
            raise HTTPException(status_code=404, detail=f"Drug not found: {drug_name}")
        if drug_ids:
            results = session.run(
                cq.CONTRAINDICATION_CHECK_CYPHER, drug_ids=drug_ids, condition=condition
            ).data()
        else:
            results = session.run(
                """
                MATCH (d:Drug)-[r:CONTRAINDICATED_FOR]->(c:Condition)
                WHERE $condition = '' OR c.name CONTAINS $condition
                RETURN d.generic_name AS drug, c.name AS condition, r.condition_type AS condition_type,
                       r.severity AS severity, r.description AS description
                ORDER BY d.generic_name
                """,
                condition=condition,
            ).data()
    return {"count": len(results), "results": results}


@app.post("/comorbidity")
def comorbidity_plans(body: ComorbidityRequest) -> dict:
    with driver.session() as session:
        plans = session.run(cq.COMORBIDITY_PLAN_CYPHER, disease_keywords=body.diseases).data()
        all_drugs: set[str] = set()
        for p in plans:
            all_drugs.update(p.get("drugs") or [])

        conflict_result = _check_interactions(list(all_drugs)) if len(all_drugs) >= 2 else {
            "interactions": [], "duplicate_classes": [], "safe": True
        }

    return {
        "diseases": body.diseases,
        "plans": plans,
        "combined_drugs": sorted(all_drugs),
        "interaction_check": conflict_result,
    }


@app.get("/path")
def find_path(drug_a: str = Query(...), drug_b: str = Query(...)) -> dict:
    with driver.session() as session:
        results = session.run(cq.PATH_CYPHER, drug_a=drug_a, drug_b=drug_b).data()
    return {"drug_a": drug_a, "drug_b": drug_b, "paths": results}


@app.post("/qa")
def qa(body: QARequest) -> dict:
    safety = assess_question(body.question)
    if safety.action == "blocked":
        return {
            "question": body.question.strip(), "intent": "safety_blocked", "answer": safety.message,
            "data": {}, "citations": [],
            "retrieval": {"strategy": "none", "grounded": False, "context_records": 0},
            "safety": safety.as_dict(),
        }
    with driver.session() as session:
        def resolve_drugs(name: str) -> list[dict[str, Any]]:
            return session.run(cq.RESOLVE_DRUG, name=name).data()

        def check_ix(drug_ids: list[str]) -> dict[str, Any]:
            interactions = [
                r for r in session.run(cq.INTERACTION_CHECK_CYPHER, drug_ids=drug_ids).data()
                if r.get("severity")
            ]
            duplicates = session.run(cq.DUPLICATE_CLASS_CYPHER, drug_ids=drug_ids).data()
            return {"interactions": interactions, "duplicate_classes": duplicates}

        def recommend(disease: str, icd: str) -> dict[str, Any]:
            results = session.run(cq.RECOMMEND_CYPHER, keyword=disease, icd=icd).data()
            return {"count": len(results), "results": results}

        def drug_info(name: str) -> dict[str, Any]:
            results = session.run(cq.DRUG_CYPHER, drug_name=name).data()
            if not results:
                raise HTTPException(status_code=404, detail="not found")
            return {"count": len(results), "results": results}

        def check_ci(drug_ids: list[str], condition: str) -> dict[str, Any]:
            results = session.run(
                cq.CONTRAINDICATION_CHECK_CYPHER, drug_ids=drug_ids, condition=condition
            ).data()
            return {"contraindications": results}

        result = answer_question(
            body.question, resolve_drugs, check_ix, recommend, drug_info, check_ci
        )
        result = build_grounded_response(result)
        result["safety"] = safety.as_dict()
        return result
