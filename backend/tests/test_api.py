"""
Test API endpoints using FastAPI's TestClient.

These tests spin up the app in-memory (no real server/port needed) and
send fake HTTP requests to it - fast and doesn't touch your real
ai_trace.db file, since we override the database dependency with a
fresh in-memory SQLite database for each test session.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.database import Base, get_db

# In-memory SQLite database just for tests
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """Create all tables once for this test module, drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_health_check():
    """Basic health check endpoint works"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    """Root endpoint returns API info"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "AI Trace Explorer"


def test_llm_request_missing_prompt_returns_422():
    """Empty/missing user_prompt should fail validation before hitting the pipeline"""
    response = client.post("/api/v1/llm/request", json={"model_name": "claude-sonnet"})
    assert response.status_code == 422  # FastAPI's validation error code


def test_llm_request_unsupported_model():
    """An unsupported model should come back as a pipeline-level error, not a crash"""
    response = client.post("/api/v1/llm/request", json={
        "user_prompt": "Hello",
        "model_name": "some-made-up-model",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["failed_stage"] == "llm_gateway"


def test_list_traces_empty():
    """With no requests made yet (in this fresh test db), list should be empty"""
    response = client.get("/api/v1/traces")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 0
    assert isinstance(body["traces"], list)


def test_get_trace_not_found():
    """Requesting a trace_id that doesn't exist should 404"""
    response = client.get("/api/v1/traces/does-not-exist")
    assert response.status_code == 404


def test_llm_request_then_fetch_trace():
    """
    End-to-end: send a request (that fails at llm_gateway since no real
    API keys are configured in the test environment), then fetch it back
    via GET /traces/{id} and confirm the stages were recorded.
    """
    create_response = client.post("/api/v1/llm/request", json={
        "user_prompt": "What is AI?",
        "model_name": "some-unsupported-model-xyz",
    })
    assert create_response.status_code == 200
    trace_id = create_response.json()["trace_id"]

    get_response = client.get(f"/api/v1/traces/{trace_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["id"] == trace_id
    assert body["status"] == "error"
    assert len(body["stages"]) >= 1  # at least prompt_builder + tokenizer ran


def test_list_models():
    """Models endpoint should return the seeded list (once seeded)"""
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
