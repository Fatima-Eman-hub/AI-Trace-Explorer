"""
Test analytics endpoints.

Uses an isolated in-memory SQLite database with StaticPool, which is
essential here: without StaticPool, SQLAlchemy may open a NEW physical
connection per query, and each new connection to sqlite:///:memory:
gets its own EMPTY database - causing "no such table" errors that only
show up when the full test suite runs together (as it does in CI),
not when this file is run alone.
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

# A dedicated engine/pool for THIS file only - StaticPool keeps a single
# shared connection alive for the life of this engine, so every session
# created from it sees the same in-memory database.
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
    # Make sure this module's overrides + schema are in place before ANY
    # test in this file runs, regardless of what other test files did.
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)

    db = TestSessionLocal()
    now = datetime.utcnow()

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

        db.add(Trace(request_id=req.id, stage_name="llm_call", stage_order=3,
                      status="success", duration_ms=200 + i * 40))
        db.add(Evaluation(
            request_id=req.id, hallucination_score=0.1, faithfulness_score=0.8,
            answer_relevancy=0.5, overall_quality_score=0.7,
            quality_level="good", needs_review=False,
        ))
        db.commit()

    req2 = Request(
        user_prompt="Free model test", model_name="gpt-oss-120b", status="success",
        timestamp=now, total_latency_ms=150, input_tokens=40, output_tokens=20, cost_usd=0.0,
    )
    db.add(req2)
    db.commit()

    req3 = Request(
        user_prompt="This one failed", model_name="claude-sonnet", status="error",
        timestamp=now, error_message="Failed at stage 'llm_call': some API error",
        failure_category="provider_error",
    )
    db.add(req3)
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)


client = TestClient(app)


def test_latency_analytics():
    response = client.get("/api/v1/analytics/latency?period=24h")
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "24h"
    assert body["summary"]["total_requests"] == 3
    assert body["summary"]["avg_latency_ms"] > 0


def test_cost_analytics():
    response = client.get("/api/v1/analytics/cost?period=24h")
    assert response.status_code == 200
    body = response.json()
    assert "claude-sonnet" in body["by_model"]
    assert body["by_model"]["claude-sonnet"]["requests"] == 3
    assert body["total_cost_usd"] > 0


def test_performance_analytics():
    response = client.get("/api/v1/analytics/performance?period=24h")
    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] == 4
    assert body["error_rate"] > 0
    assert body["errors"]["total_errors"] == 1
    assert "llm_call" in body["errors"]["by_stage"]
    assert body["errors"]["by_category"].get("provider_error") == 1
    assert body["quality"]["good_count"] == 2


def test_invalid_period_rejected():
    response = client.get("/api/v1/analytics/latency?period=invalid")
    assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])