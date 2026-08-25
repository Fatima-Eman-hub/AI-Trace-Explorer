"""
Test models - verify database models work correctly
"""

import pytest
from app.models import Request, Trace, Evaluation, SupportedModel
from app.database import Base, SessionLocal, engine
import uuid


@pytest.fixture
def setup_db():
    """Setup test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_request_model(setup_db):
    """Test Request model"""
    db = SessionLocal()

    request = Request(
        id=str(uuid.uuid4()),
        user_prompt="What is AI?",
        model_name="claude-sonnet",
        status="success",
        total_latency_ms=245,
        input_tokens=100,
        output_tokens=150,
        cost_usd=0.002,
    )

    db.add(request)
    db.commit()
    db.refresh(request)

    fetched = db.query(Request).filter(Request.id == request.id).first()
    assert fetched is not None
    assert fetched.user_prompt == "What is AI?"
    assert fetched.model_name == "claude-sonnet"
    assert fetched.status == "success"
    assert fetched.total_latency_ms == 245

    db.close()


def test_trace_model(setup_db):
    """Test Trace model"""
    db = SessionLocal()

    request_id = str(uuid.uuid4())
    request = Request(id=request_id, user_prompt="Test", model_name="claude-sonnet")
    db.add(request)
    db.commit()

    trace = Trace(
        id=str(uuid.uuid4()),
        request_id=request_id,
        stage_name="prompt_builder",
        stage_order=0,
        status="success",
        duration_ms=10,
        stage_input={"prompt": "What is AI?"},
        stage_output={"formatted_prompt": "Format..."},
    )

    db.add(trace)
    db.commit()
    db.refresh(trace)

    fetched = db.query(Trace).filter(Trace.id == trace.id).first()
    assert fetched is not None
    assert fetched.stage_name == "prompt_builder"
    assert fetched.duration_ms == 10

    db.close()


def test_evaluation_model(setup_db):
    """Test Evaluation model"""
    db = SessionLocal()

    request_id = str(uuid.uuid4())
    request = Request(id=request_id, user_prompt="Test", model_name="claude-sonnet")
    db.add(request)
    db.commit()

    evaluation = Evaluation(
        id=str(uuid.uuid4()),
        request_id=request_id,
        hallucination_score=0.05,
        faithfulness_score=0.92,
        answer_relevancy=0.95,
        overall_quality_score=0.91,
        quality_level="excellent",
    )

    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)

    fetched = db.query(Evaluation).filter(Evaluation.id == evaluation.id).first()
    assert fetched is not None
    assert fetched.hallucination_score == 0.05
    assert fetched.quality_level == "excellent"

    db.close()


def test_supported_model(setup_db):
    """Test SupportedModel"""
    db = SessionLocal()

    model = SupportedModel(
        id=str(uuid.uuid4()),
        name="claude-sonnet",
        provider="anthropic",
        max_context_tokens=200000,
        input_price_per_1k=0.003,
        output_price_per_1k=0.006,
        is_active=True,
        is_available=True,
        description="Fast and efficient",
    )

    db.add(model)
    db.commit()
    db.refresh(model)

    fetched = db.query(SupportedModel).filter(SupportedModel.name == "claude-sonnet").first()
    assert fetched is not None
    assert fetched.provider == "anthropic"
    assert fetched.max_context_tokens == 200000

    cost = fetched.calculate_cost(1000, 1000)
    expected_cost = (1000 / 1000) * 0.003 + (1000 / 1000) * 0.006
    assert cost == expected_cost

    db.close()


def test_request_relationships(setup_db):
    """Test relationships between models"""
    db = SessionLocal()

    request_id = str(uuid.uuid4())
    request = Request(id=request_id, user_prompt="Test", model_name="claude-sonnet")

    trace1 = Trace(
        id=str(uuid.uuid4()), request_id=request_id,
        stage_name="prompt_builder", stage_order=0, status="success", duration_ms=10,
    )
    trace2 = Trace(
        id=str(uuid.uuid4()), request_id=request_id,
        stage_name="tokenizer", stage_order=1, status="success", duration_ms=20,
    )
    evaluation = Evaluation(
        id=str(uuid.uuid4()), request_id=request_id, hallucination_score=0.05,
    )

    db.add_all([request, trace1, trace2, evaluation])
    db.commit()

    fetched_request = db.query(Request).filter(Request.id == request_id).first()
    assert len(fetched_request.traces) == 2
    assert len(fetched_request.evaluations) == 1
    assert fetched_request.traces[0].stage_name == "prompt_builder"

    db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
