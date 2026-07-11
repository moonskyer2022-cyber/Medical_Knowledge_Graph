"""Pharma knowledge graph recommendation API."""

import os
import time
import uuid
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

from api import cypher as cq
from api.audit import append_audit_event, recent_audit_events
from api.auth import AuthUser, AuthenticationError, authentication_enabled, issue_token, user_from_authorization, verify_credentials
from api.graph_builder import build_disease_graph, build_drug_graph
from api.qa import answer_question
from api.rag import build_grounded_response
from api.safety import assess_question, safety_response
from api.source_registry import get_source_by_id, list_source_reviews, load_source_registry, record_source_review
from api.observability import allow_request, log_request, rate_limit_enabled

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
load_dotenv(ROOT / ".env")

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
APP_ENV = os.getenv("APP_ENV", "demo").strip().lower()
PASSWORD = os.getenv("NEO4J_PASSWORD", "")
if APP_ENV == "production" and not PASSWORD:
    raise RuntimeError("NEO4J_PASSWORD must be configured when APP_ENV=production")
PASSWORD = PASSWORD or "password"
driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


def configured_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


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
app.add_middleware(CORSMiddleware, allow_origins=configured_origins(), allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])

if WEB.exists():
    app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


class InteractionRequest(BaseModel):
    drug_names: list[str] = Field(..., min_length=2, description="至少两种药品名称")


class ComorbidityRequest(BaseModel):
    diseases: list[str] = Field(..., min_length=1, description="疾病名称列表")


class QARequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)


class TokenRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=256)


class SourceReviewRequest(BaseModel):
    review_type: str = Field(..., pattern="^(metadata|clinical_content)$")
    outcome: str = Field(..., pattern="^(approved|needs_revision|rejected)$")
    evidence_url: str = Field("", max_length=2000)
    evidence_excerpt: str = Field("", max_length=2000)
    notes: str = Field("", max_length=4000)
    next_review_due: str = Field("", max_length=20)


PUBLIC_PATHS = {"/", "/api", "/health", "/docs", "/openapi.json", "/auth/token"}


@app.middleware("http")
async def authentication_and_audit(request: Request, call_next):
    request_id = uuid.uuid4().hex
    started = time.perf_counter()
    user = AuthUser("anonymous", ())
    path = request.url.path
    protected = path not in PUBLIC_PATHS and not path.startswith("/static")
    if rate_limit_enabled() and path in {"/auth/token", "/qa"}:
        key = f"{request.client.host if request.client else 'unknown'}:{path}"
        if not allow_request(key):
            response = JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})
            response.headers["X-Request-ID"] = request_id
            return response
    if authentication_enabled() and protected:
        try:
            user = user_from_authorization(request.headers.get("Authorization"))
        except AuthenticationError as exc:
            response = JSONResponse(status_code=401, content={"detail": str(exc)})
            response.headers["X-Request-ID"] = request_id
            append_audit_event({"request_id": request_id, "user": "anonymous", "action": path, "method": request.method, "status_code": 401, "duration_ms": round((time.perf_counter() - started) * 1000, 2)})
            return response
    request.state.user = user
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-ms"] = str(round((time.perf_counter() - started) * 1000, 2))
    log_request(request_id=request_id, method=request.method, path=path, status_code=response.status_code, user=user.username, duration_ms=round((time.perf_counter() - started) * 1000, 2))
    if protected:
        append_audit_event({"request_id": request_id, "user": user.username, "roles": list(user.roles), "action": path, "method": request.method, "status_code": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000, 2)})
    return response


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
            "/contraindications", "/comorbidity", "/path", "/qa", "/auth/token", "/sources", "/audit/recent",
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


@app.post("/auth/token")
def create_token(body: TokenRequest) -> dict:
    if not authentication_enabled():
        raise HTTPException(status_code=409, detail="authentication is disabled")
    try:
        user = verify_credentials(body.username, body.password)
        append_audit_event({"user": user.username, "action": "/auth/token", "method": "POST", "status_code": 200, "roles": list(user.roles)})
        return {"access_token": issue_token(user), "token_type": "bearer", "roles": user.roles}
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/audit/recent")
def audit_recent(request: Request, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0, le=10000)) -> dict:
    user: AuthUser = request.state.user
    if not authentication_enabled() or "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="administrator role required")
    events = recent_audit_events(limit, offset)
    return {"count": len(events), "offset": offset, "events": events}


@app.get("/sources")
def sources() -> dict:
    registry = list(load_source_registry().values())
    return {"count": len(registry), "sources": registry}


@app.get("/sources/{source_id}/reviews")
def source_reviews(source_id: str) -> dict:
    if not get_source_by_id(source_id):
        raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
    reviews = list_source_reviews(source_id, limit=100)
    return {"source_id": source_id, "count": len(reviews), "reviews": reviews}


@app.post("/sources/{source_id}/reviews")
def review_source(source_id: str, body: SourceReviewRequest, request: Request) -> dict:
    user: AuthUser = request.state.user
    if not authentication_enabled() or "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="administrator role required")
    if body.review_type == "clinical_content" and not ({"admin", "clinical_reviewer"} & set(user.roles)):
        raise HTTPException(status_code=403, detail="clinical reviewer role required")
    if body.review_type == "metadata" and not ({"admin", "data_steward"} & set(user.roles)):
        raise HTTPException(status_code=403, detail="data steward role required")
    try:
        review_id, source = record_source_review(source_id, body.review_type, user.username, "clinical_reviewer" if body.review_type == "clinical_content" else "data_steward", body.outcome, body.evidence_url, body.evidence_excerpt, body.notes, body.next_review_due)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"review_id": review_id, "source": source}


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
            "safety": safety_response(safety),
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
        result["safety"] = safety_response(safety)
        return result
