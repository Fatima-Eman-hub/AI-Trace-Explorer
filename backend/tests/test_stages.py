"""
Test stages - verify individual stages and the full pipeline work

Note: test_llm_call_stage and test_full_pipeline_with_real_api require a
valid ANTHROPIC_API_KEY or GROQ_API_KEY in .env - they are marked to skip
automatically if neither key is set, so the rest of the suite still runs
offline.
"""

import pytest
from app.stages import (
    PromptBuilderStage,
    TokenizerStage,
    LLMGatewayStage,
    ResponseParserStage,
    CostCalculatorStage,
)
from app.config import settings


def test_prompt_builder_basic():
    stage = PromptBuilderStage()
    output = stage.run({"user_prompt": "What is AI?"})
    assert output["formatted_prompt"] == "What is AI?"
    assert output["num_few_shot_examples"] == 0


def test_prompt_builder_with_few_shot():
    stage = PromptBuilderStage()
    output = stage.run({
        "user_prompt": "What is ML?",
        "few_shot_examples": [
            {"input": "What is AI?", "output": "AI is..."}
        ],
    })
    assert "What is AI?" in output["formatted_prompt"]
    assert "What is ML?" in output["formatted_prompt"]
    assert output["num_few_shot_examples"] == 1


def test_prompt_builder_empty_prompt_fails():
    stage = PromptBuilderStage()
    with pytest.raises(ValueError):
        stage.run({"user_prompt": ""})


def test_tokenizer_estimates_tokens():
    stage = TokenizerStage()
    output = stage.run({
        "formatted_prompt": "What is artificial intelligence?",
        "system_prompt": "",
    })
    assert output["estimated_input_tokens"] > 0
    assert output["estimated_output_tokens"] > 0
    assert "context_window_used_pct" in output


def test_llm_gateway_resolves_claude():
    stage = LLMGatewayStage()
    output = stage.run({
        "model_name": "claude-sonnet",
        "model_parameters": {"temperature": 0.5},
    })
    assert output["provider"] == "anthropic"
    assert output["resolved_parameters"]["temperature"] == 0.5
    assert output["resolved_parameters"]["max_tokens"] == 1024


def test_llm_gateway_resolves_groq():
    stage = LLMGatewayStage()
    output = stage.run({"model_name": "llama-3.3-70b"})
    assert output["provider"] == "groq"


def test_llm_gateway_unsupported_model_fails():
    stage = LLMGatewayStage()
    with pytest.raises(ValueError):
        stage.run({"model_name": "some-unknown-model"})


def test_response_parser_cleans_response():
    stage = ResponseParserStage()
    output = stage.run({
        "response_text": "  AI is the simulation of human intelligence.  ",
        "stop_reason": "end_turn",
    })
    assert output["clean_response"] == "AI is the simulation of human intelligence."
    assert output["was_truncated"] is False
    assert output["is_empty"] is False


def test_response_parser_empty_response_fails():
    stage = ResponseParserStage()
    with pytest.raises(ValueError):
        stage.run({"response_text": "", "stop_reason": "end_turn"})


def test_cost_calculator():
    stage = CostCalculatorStage()
    output = stage.run({
        "model_name": "claude-sonnet",
        "actual_input_tokens": 1000,
        "actual_output_tokens": 1000,
    })
    assert output["input_cost_usd"] == 0.003
    assert output["output_cost_usd"] == 0.015
    assert output["total_cost_usd"] == 0.018


def test_cost_calculator_groq_is_free():
    stage = CostCalculatorStage()
    output = stage.run({
        "model_name": "llama-3.3-70b",
        "actual_input_tokens": 1000,
        "actual_output_tokens": 1000,
    })
    assert output["total_cost_usd"] == 0.0


@pytest.mark.skipif(
    not (settings.anthropic_api_key or settings.groq_api_key),
    reason="No ANTHROPIC_API_KEY or GROQ_API_KEY set",
)
def test_full_pipeline_with_real_api():
    """
    Integration test: runs the FULL 7-stage pipeline against a real API
    (prefers Groq since it's free). Only runs if a key is configured.
    """
    from app.database import Base, SessionLocal, engine
    from app.pipeline import PipelineOrchestrator

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    model_name = "llama-3.3-70b" if settings.groq_api_key else "claude-sonnet"

    orchestrator = PipelineOrchestrator()
    result = orchestrator.run(
        db=db,
        user_prompt="Say hello in exactly 3 words.",
        model_name=model_name,
    )

    assert result["status"] == "success"
    assert len(result["stages"]) == 7  # now includes the evaluator stage
    assert result["metrics"]["cost_usd"] >= 0
    assert len(result["response"]) > 0
    assert "evaluation" in result
    assert result["evaluation"]["quality_level"] in ("excellent", "good", "fair", "poor")

    db.close()
    Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
