from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DB_PATH = Path(__file__).resolve().parent / "test_chiron.db"
os.environ["CHIRON_DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["CHIRON_LLM_MODE"] = "heuristic"
os.environ["CHIRON_LITERATURE_CONNECTOR_MODE"] = "mock"
os.environ["CHIRON_TRIALS_CONNECTOR_MODE"] = "mock"
os.environ["CHIRON_DRUG_SAFETY_CONNECTOR_MODE"] = "mock"
os.environ["CHIRON_GUIDELINE_CONNECTOR_MODE"] = "mock"

from app.main import create_app  # noqa: E402


def test_health_endpoint() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["llm_mode"] == "heuristic"


def test_create_session_and_answered_flow() -> None:
    with TestClient(create_app()) as client:
        session_response = client.post("/api/sessions", json={"title": "Backend scaffold demo"})
        assert session_response.status_code == 200
        session_id = session_response.json()["id"]

        response = client.post(
            f"/api/sessions/{session_id}/messages",
            json={
                "role": "user",
                "content": "Latest treatment for drug-resistant TB in pregnancy, and major safety concerns.",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["response"]["status"] == "answered"
        assert payload["response"]["citations"]

        run_id = payload["run_id"]
        steps_response = client.get(f"/api/runs/{run_id}/steps")
        assert steps_response.status_code == 200
        step_names = [step["node_name"] for step in steps_response.json()]
        assert "parse_query" in step_names
        assert "verify_answer" in step_names


def test_clarification_flow() -> None:
    with TestClient(create_app()) as client:
        session_response = client.post("/api/sessions", json={})
        session_id = session_response.json()["id"]
        response = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"role": "user", "content": "Best treatment for pneumonia?"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["response"]["status"] == "needs_clarification"
        assert payload["response"]["clarification_question"]
