"""
Test API endpoints using FastAPI's TestClient.

IMPORTANT TEST-ISOLATION NOTE: app.dependency_overrides is a single
shared dict on the `app` singleton, and pytest imports ALL test modules
during collection before running ANY tests. That means if this file set
its override at MODULE level (outside a fixture), it would fire at
import time - and whichever test file's autouse fixture runs LAST right
before its own tests would need to re-assert its own override, or an
earlier file's teardown (e.g. popping the override) could leave this
file with no override at all, silently falling through to the REAL
production database (which has no tables created in CI). To avoid this,
we set (and re-set) the override INSIDE this module's own autouse
fixture, immediately before this file's tests run - never at import time.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.database import Base, get_db

engine = create_engine(
    "sqlite:///:memory:",
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


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    # Re-assert OUR override right before OUR tests run, regardless of
    # what any other test file's fixture did before or after us.
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "AI Trace Explorer"


def test_llm_request_missing_prompt_returns_422():
    response = client.post("/api/v1/llm/request", json={"model_name": "claude-sonnet"})
    assert response.status_code == 422


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
    response = client.get("/api/v1/traces")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 0
    assert isinstance(body["traces"], list)


def test_get_trace_not_found():
    response = client.get("/api/v1/traces/does-not-exist")
    assert response.status_code == 404


def test_llm_request_then_fetch_trace():
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
    assert len(body["stages"]) >= 1


def test_list_models():
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])