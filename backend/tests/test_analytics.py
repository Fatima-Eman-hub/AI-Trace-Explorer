"""
Test analytics endpoints.

Rather than calling real LLM APIs, we insert sample Request/Trace/
Evaluation rows directly into a fresh in-memory test database, then
verify the analytics endpoints aggregate them correctly.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.database import Base, get_db
from app.models import Request, Trace, Evaluation

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
    Base.metadata.create_all(bind=engine)

    db = TestSessionLocal()
    now = datetime.utcnow()

    # Two successful requests on claude-sonnet
    for i in range(2):
        req = Request(
            user_prompt=f"Test prompt {i}",
            model_name="claude-sonnet",
            status="success",
            timestamp=now - timedelta(minutes=i * 5),
            total_latency_ms=300 + i * 50,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.002,
        )
        db.add(req)
        db.commit()
        db.refresh(req)

        db.add(Trace(
            request_id=req.id, stage_name="llm_call", stage_order=3,
            status="success", duration_ms=200 + i * 40,
        ))
        db.add(Evaluation(
            request_id=req.id,
            hallucination_score=0.1, faithfulness_score=0.8, answer_relevancy=0.5,
            overall_quality_score=0.7, quality_level="good", needs_review=False,
        ))
        db.commit()

    # One successful request on a free groq model
    req2 = Request(
        user_prompt="Free model test",
        model_name="llama-3.3-70b",
        status="success",
        timestamp=now,
        total_latency_ms=150,
        input_tokens=40,
        output_tokens=20,
        cost_usd=0.0,
    )
    db.add(req2)
    db.commit()

    # One failed request
    req3 = Request(
        user_prompt="This one failed",
        model_name="claude-sonnet",
        status="error",
        timestamp=now,
        error_message="Failed at stage 'llm_call': some API error",
    )
    db.add(req3)
    db.commit()
    db.close()

    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_latency_analytics():
    response = client.get("/api/v1/analytics/latency?period=24h")
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "24h"
    assert body["summary"]["total_requests"] == 3  # 2 claude + 1 groq (successful only)
    assert body["summary"]["avg_latency_ms"] > 0


def test_cost_analytics():
    response = client.get("/api/v1/analytics/cost?period=24h")
    assert response.status_code == 200
    body = response.json()
    assert "claude-sonnet" in body["by_model"]
    # 2 successful claude-sonnet requests + 1 errored one (which still has
    # cost_usd=0.0 as its default, since the error happened before any
    # tokens were spent) = 3 total requests attributed to this model.
    assert body["by_model"]["claude-sonnet"]["requests"] == 3
    assert body["total_cost_usd"] > 0


def test_performance_analytics():
    response = client.get("/api/v1/analytics/performance?period=24h")
    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] == 4  # 3 success + 1 error
    assert body["error_rate"] > 0
    assert body["errors"]["total_errors"] == 1
    assert "llm_call" in body["errors"]["by_stage"]
    assert body["quality"]["good_count"] == 2


def test_invalid_period_rejected():
    response = client.get("/api/v1/analytics/latency?period=invalid")
    assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
