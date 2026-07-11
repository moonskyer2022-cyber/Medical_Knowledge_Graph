import shutil

from api import main
from api.auth import AuthUser, issue_token, user_from_authorization
from api.audit import append_audit_event
from api.observability import allow_request
from api import source_registry
from starlette.testclient import TestClient


def test_token_round_trip(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "x" * 40)
    token = issue_token(AuthUser("tester", ("admin",)))
    assert user_from_authorization(f"Bearer {token}").username == "tester"


def test_auth_middleware_blocks_protected_route(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    response = TestClient(main.app).get("/sources")
    assert response.status_code == 401
    monkeypatch.setenv("AUTH_ENABLED", "false")


def test_audit_does_not_write_when_disabled(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("AUDIT_ENABLED", "false")
    monkeypatch.setenv("AUDIT_LOG_PATH", str(path))
    append_audit_event({"question": "secret clinical content"})
    assert not path.exists()


def test_audit_filters_clinical_content_when_enabled(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("AUDIT_ENABLED", "true")
    monkeypatch.setenv("AUDIT_LOG_PATH", str(path))
    append_audit_event({"request_id": "r1", "action": "/qa", "question": "secret clinical content", "password": "secret"})
    content = path.read_text(encoding="utf-8")
    assert "secret clinical content" not in content
    assert "password" not in content
    assert '"action":"/qa"' in content


def test_audit_log_rotates_at_configured_size(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("AUDIT_ENABLED", "true")
    monkeypatch.setenv("AUDIT_LOG_PATH", str(path))
    monkeypatch.setenv("AUDIT_MAX_BYTES", "1")
    append_audit_event({"action": "/first"})
    append_audit_event({"action": "/second"})
    assert path.with_suffix(".jsonl.1").exists()
    assert '"action":"/second"' in path.read_text(encoding="utf-8")


def test_source_review_endpoint_requires_admin(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    response = TestClient(main.app).post("/sources/SRC-001/reviews", json={"review_type": "metadata", "outcome": "approved", "evidence_url": "https://example.com"})
    assert response.status_code == 403


def test_source_review_enforces_role_scope(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_SECRET", "x" * 40)
    token = issue_token(AuthUser("steward", ("data_steward",)))
    response = TestClient(main.app).post(
        "/sources/SRC-004/reviews",
        headers={"Authorization": f"Bearer {token}"},
        json={"review_type": "clinical_content", "outcome": "rejected"},
    )
    assert response.status_code == 403
    monkeypatch.setenv("AUTH_ENABLED", "false")


def test_invalid_token_is_rejected(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_SECRET", "x" * 40)
    response = TestClient(main.app).get("/audit/recent", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    monkeypatch.setenv("AUTH_ENABLED", "false")


def test_rate_limit_rejects_after_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    assert allow_request("test-rate", limit=1, window_seconds=60)
    assert not allow_request("test-rate", limit=1, window_seconds=60)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")


def test_response_contains_observability_headers(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    response = TestClient(main.app).get("/api")
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Process-Time-ms"]


def test_admin_can_record_metadata_review(tmp_path, monkeypatch):
    registry_path = tmp_path / "source_registry.csv"
    reviews_path = tmp_path / "source_reviews.csv"
    shutil.copyfile(source_registry.REGISTRY_PATH, registry_path)
    monkeypatch.setattr(source_registry, "REGISTRY_PATH", registry_path)
    monkeypatch.setattr(source_registry, "REVIEWS_PATH", reviews_path)
    source_registry.clear_source_registry_cache()
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_SECRET", "x" * 40)
    token = issue_token(AuthUser("reviewer", ("admin", "data_steward")))
    response = TestClient(main.app).post(
        "/sources/SRC-004/reviews",
        headers={"Authorization": f"Bearer {token}"},
        json={"review_type": "metadata", "outcome": "approved", "evidence_url": "https://example.com/source", "evidence_excerpt": "公开发布记录", "notes": "metadata checked"},
    )
    assert response.status_code == 200
    assert response.json()["source"]["verification_status"] == "metadata_verified"
    history = TestClient(main.app).get("/sources/SRC-004/reviews", headers={"Authorization": f"Bearer {token}"})
    assert history.status_code == 200
    assert history.json()["count"] == 1
    monkeypatch.setenv("AUTH_ENABLED", "false")
    source_registry.clear_source_registry_cache()
