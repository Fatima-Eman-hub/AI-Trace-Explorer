"""
Test the Evaluator stage's heuristic scoring functions.
"""

import pytest
from app.stages.evaluator import (
    tokenize,
    cosine_similarity,
    compute_hallucination_score,
    compute_faithfulness_score,
    EvaluatorStage,
)


def test_tokenize_removes_stopwords_and_punctuation():
    result = tokenize("The AI is very helpful, isn't it?")
    assert "the" not in result
    assert "is" not in result
    assert "ai" in result
    assert "helpful" in result


def test_cosine_similarity_identical_text():
    """Identical texts should score close to 1.0"""
    score = cosine_similarity("artificial intelligence machine learning", "artificial intelligence machine learning")
    assert score == 1.0


def test_cosine_similarity_unrelated_text():
    """Completely unrelated texts should score low"""
    score = cosine_similarity("cats and dogs are pets", "quantum physics equations")
    assert score < 0.2


def test_cosine_similarity_related_text():
    """Related texts should score somewhere in the middle-high range"""
    score = cosine_similarity(
        "What is artificial intelligence?",
        "Artificial intelligence is the simulation of human intelligence by machines.",
    )
    assert 0.2 < score <= 1.0


def test_hallucination_score_no_numbers():
    """A response with no specific claims should score 0 (nothing to verify)"""
    score = compute_hallucination_score("Tell me about AI", "AI is a broad field of computer science.")
    assert score == 0.0


def test_hallucination_score_grounded_numbers():
    """Numbers that appear in the prompt shouldn't count as hallucinated"""
    score = compute_hallucination_score(
        "In 2023, how many parameters did GPT-4 have?",
        "In 2023, GPT-4 was released.",
    )
    assert score == 0.0  # "2023" appears in both


def test_hallucination_score_unverifiable_numbers():
    """Numbers NOT in the prompt should be flagged as unverifiable"""
    score = compute_hallucination_score(
        "Tell me about the moon landing",
        "The moon landing happened in 1969 and involved 3 astronauts traveling 384400 km.",
    )
    assert score > 0.5  # most/all numeric claims are unverifiable from the prompt alone


def test_faithfulness_no_context_returns_neutral():
    """With no system_prompt, faithfulness should default to a neutral value"""
    score = compute_faithfulness_score("", "Some response text here.")
    assert score == 0.85


def test_faithfulness_with_matching_context():
    """Response that echoes the system_prompt's terms should score higher"""
    score = compute_faithfulness_score(
        "Only discuss cooking recipes and ingredients",
        "Here is a recipe with ingredients for a great dish.",
    )
    assert score > 0.0


def test_evaluator_stage_full_run():
    """Full EvaluatorStage.run() produces all expected fields"""
    stage = EvaluatorStage()
    output = stage.run({
        "user_prompt": "What is AI?",
        "system_prompt": "",
        "clean_response": "AI is the simulation of human intelligence by machines.",
    })

    assert "hallucination_score" in output
    assert "faithfulness_score" in output
    assert "answer_relevancy" in output
    assert "overall_quality_score" in output
    assert output["quality_level"] in ("excellent", "good", "fair", "poor")
    assert isinstance(output["needs_review"], bool)


def test_evaluator_stage_empty_response_fails():
    """Empty response should raise an error, not silently score it"""
    stage = EvaluatorStage()
    with pytest.raises(ValueError):
        stage.run({"user_prompt": "Hi", "system_prompt": "", "clean_response": ""})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
