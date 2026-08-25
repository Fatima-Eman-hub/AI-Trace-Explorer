"""
Evaluator Stage - Stage 6 of the pipeline

Job: Score the quality of the LLM's response using lightweight,
     dependency-free heuristics:
       - answer_relevancy: does the response actually address the prompt?
       - hallucination_score: does the response make suspicious,
         unverifiable specific claims (numbers/dates/stats) that weren't
         grounded in the prompt or system_prompt?
       - faithfulness_score: if a system_prompt/context was given, does
         the response stick to it? (If no context was given, there's
         nothing to be "unfaithful" to, so we return a neutral score.)

NOTE ON APPROACH: These are pure-Python word-overlap heuristics, not a
real embedding/NLI model. They're intentionally dependency-free (no
torch/transformers/sklearn) to avoid the install issues heavier ML
libraries can cause. To partially compensate for the biggest weakness
of raw keyword overlap - questions and answers naturally use different
words (e.g. "AI" vs "Artificial Intelligence") - we apply two small
normalization steps before comparing text: acronym expansion and light
suffix-stemming. This is still not true semantic similarity; a future
upgrade could swap these functions for sentence-transformers cosine
similarity or an NLI entailment model without changing anything else
in the pipeline.
"""

import math
import re
from collections import Counter
from typing import Any, Dict, List
from app.stages.base import BaseStage


# A small stopword list - common words we don't want polluting our
# word-overlap comparisons (not exhaustive, just enough to be useful).
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "then", "so", "to", "of", "in", "on", "at",
    "for", "with", "as", "by", "from", "this", "that", "these", "those",
    "it", "its", "i", "you", "he", "she", "we", "they", "them", "my",
    "your", "his", "her", "our", "their", "do", "does", "did", "will",
    "would", "can", "could", "should", "has", "have", "had", "not", "no",
    "refers", "refer", "typically", "such",
}

# Small acronym/abbreviation expansion map - covers common tech/AI terms
# that questions and answers phrase differently (e.g. prompt says "AI",
# response spells out "Artificial Intelligence"). Domain-tuned since this
# is an AI-focused project; extend this list as new patterns show up.
ACRONYM_EXPANSIONS = {
    "ai": ["artificial", "intelligence"],
    "ml": ["machine", "learning"],
    "nlp": ["natural", "language", "processing"],
    "llm": ["large", "language", "model"],
    "llms": ["large", "language", "model"],
    "api": ["application", "programming", "interface"],
    "ui": ["user", "interface"],
    "ux": ["user", "experience"],
}


def simple_stem(word: str) -> str:
    """
    Very small suffix-stripper - NOT a real Porter stemmer, just enough
    to match common variants like learn/learning, compute/computing,
    system/systems. Good enough for a lightweight overlap heuristic.
    """
    for suffix in ("ational", "tional", "ization", "ing", "ers", "er", "ed", "ly", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> List[str]:
    """
    Lowercase, strip punctuation, split into words, drop stopwords,
    expand known acronyms, and lightly stem each word.
    """
    if not text:
        return []
    words = re.findall(r"[a-zA-Z0-9']+", text.lower())
    words = [w for w in words if w not in STOPWORDS and len(w) > 1]

    expanded: List[str] = []
    for w in words:
        expanded.append(simple_stem(w))
        if w in ACRONYM_EXPANSIONS:
            expanded.extend(simple_stem(x) for x in ACRONYM_EXPANSIONS[w])
    return expanded


def cosine_similarity(text_a: str, text_b: str) -> float:
    """
    Cosine similarity between two texts, treating each as a bag-of-words
    frequency vector (after acronym expansion + stemming). Returns 0.0
    (no overlap) to 1.0 (identical word distribution). Pure Python - no
    numpy/sklearn needed.
    """
    words_a = tokenize(text_a)
    words_b = tokenize(text_b)

    if not words_a or not words_b:
        return 0.0

    vec_a = Counter(words_a)
    vec_b = Counter(words_b)

    shared_words = set(vec_a.keys()) & set(vec_b.keys())
    dot_product = sum(vec_a[w] * vec_b[w] for w in shared_words)

    magnitude_a = math.sqrt(sum(count ** 2 for count in vec_a.values()))
    magnitude_b = math.sqrt(sum(count ** 2 for count in vec_b.values()))

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return round(dot_product / (magnitude_a * magnitude_b), 4)


# Patterns that suggest a "specific, checkable claim" - numbers, years,
# percentages. Lots of these NOT traceable back to the prompt is a signal
# (not proof) that the model may be inventing precise-sounding details.
CLAIM_PATTERNS = [
    r"\b\d{4}\b",           # years like 1995, 2023
    r"\b\d+(\.\d+)?%\b",    # percentages like 42% or 3.5%
    r"\b\d+(\.\d+)?\b",     # any other number
]


def compute_hallucination_score(user_prompt: str, response: str) -> float:
    """
    Heuristic: what fraction of the response's specific numeric/date
    claims do NOT appear anywhere in the user's prompt? A high fraction
    of "unverifiable" specific claims is treated as a hallucination risk.

    Returns 0.0 (no risky claims) to 1.0 (all claims unverifiable).
    """
    response_claims = re.findall(r"\d+(?:\.\d+)?%?", response)
    if not response_claims:
        return 0.0  # no specific claims made = nothing to hallucinate about

    prompt_text = user_prompt.lower()
    unverifiable = [c for c in response_claims if c.lower() not in prompt_text]

    return round(len(unverifiable) / len(response_claims), 4)


def compute_faithfulness_score(system_prompt: str, response: str) -> float:
    """
    If a system_prompt/context was provided, measure how much the
    response's content overlaps with it (a proxy for "staying grounded").
    If no context was given, there's nothing to check faithfulness
    against, so we return a neutral-high default rather than penalizing
    the response for something it was never given.
    """
    if not system_prompt or not system_prompt.strip():
        return 0.85  # neutral default - no context = nothing to be unfaithful to

    return cosine_similarity(system_prompt, response)


class EvaluatorStage(BaseStage):
    """
    Scores the quality of the LLM response.

    Input expected:
        {
            "user_prompt": "What is AI?",
            "system_prompt": "You are helpful" (optional),
            "clean_response": "AI is..."
        }

    Output produced:
        {
            "hallucination_score": 0.0,
            "faithfulness_score": 0.85,
            "answer_relevancy": 0.40,
            "overall_quality_score": 0.72,
            "quality_level": "good",
            "needs_review": false
        }
    """

    def __init__(self):
        super().__init__(stage_name="evaluator")

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        user_prompt = input_data.get("user_prompt", "")
        system_prompt = input_data.get("system_prompt", "") or ""
        response = input_data.get("clean_response", "")

        if not response:
            raise ValueError("clean_response is required for evaluation")

        answer_relevancy = cosine_similarity(user_prompt, response)
        hallucination_score = compute_hallucination_score(user_prompt, response)
        faithfulness_score = compute_faithfulness_score(system_prompt, response)

        overall_quality_score = round(
            0.4 * answer_relevancy
            + 0.3 * (1 - hallucination_score)
            + 0.3 * faithfulness_score,
            4,
        )

        quality_level = self._quality_level(overall_quality_score)
        needs_review = hallucination_score >= 0.5 or answer_relevancy < 0.15

        return {
            "hallucination_score": hallucination_score,
            "faithfulness_score": faithfulness_score,
            "answer_relevancy": answer_relevancy,
            "overall_quality_score": overall_quality_score,
            "quality_level": quality_level,
            "needs_review": needs_review,
            "evaluation_model": "heuristic-v2-synonym-aware",
        }

    def _quality_level(self, score: float) -> str:
        if score >= 0.75:
            return "excellent"
        elif score >= 0.55:
            return "good"
        elif score >= 0.35:
            return "fair"
        else:
            return "poor"