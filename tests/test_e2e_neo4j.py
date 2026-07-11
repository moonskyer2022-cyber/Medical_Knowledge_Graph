"""End-to-end checks against a real Neo4j instance.

Set E2E_NEO4J=1 after running scripts/clean.py and scripts/import_neo4j.py.
The GitHub Actions workflow provides that environment automatically.
"""

import os

import pytest
from starlette.testclient import TestClient


pytestmark = pytest.mark.skipif(
    os.getenv("E2E_NEO4J") != "1",
    reason="requires a prepared Neo4j instance (set E2E_NEO4J=1)",
)


def test_graph_backed_demo_flow():
    from api.main import app

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        stats = client.get("/stats")
        assert stats.status_code == 200
        assert stats.json()["drugs"] >= 15
        assert stats.json()["plans"] >= 9

        recommendation = client.get("/recommend", params={"disease": "高血压"})
        assert recommendation.status_code == 200
        assert recommendation.json()["count"] >= 1

        interaction = client.get("/interactions", params={"drugs": "阿司匹林,氯吡格雷"})
        assert interaction.status_code == 200
        assert interaction.json()["interactions"]
