"""
Failure Classifier - categorizes pipeline errors and suggests root-cause fixes.

NOTE ON APPROACH: This is a rule-based classifier (regex/keyword matching
on the failed stage + error text) - not an LLM judge. This matches the
same dependency-free philosophy as the evaluator stage: it's honest
about being a heuristic, and the categories/rules can later be
supplemented with an LLM-based judge for nuanced cases the rules miss
(those fall into "unclassified" today) without changing anything else
in the pipeline.
"""

import re
from typing import Dict, NamedTuple


class Classification(NamedTuple):
    category: str
    evidence: str
    suggested_fix: str


# Category -> human-readable root-cause hint, shown to the developer.
SUGGESTED_FIXES: Dict[str, str] = {
    "invalid_input": "The prompt was empty or malformed - validate user_prompt before sending.",
    "unsupported_model": "That model name isn't registered - check GET /api/v1/models for the current supported list.",
    "authentication_error": "The provider's API key is missing, invalid, or expired - check the relevant key in .env.",
    "rate_limit_exceeded": "You've hit the provider's rate limit - add retry-with-backoff, or slow down request frequency.",
    "model_unavailable": "The provider deprecated or renamed this model ID - check their docs and update llm_call.py.",
    "network_timeout": "The request to the provider timed out - retry, or increase the client timeout.",
    "empty_response": "The model returned no usable text - try a lower temperature or rephrase the prompt.",
    "evaluation_error": "The evaluator stage itself failed - check the response text isn't empty or malformed.",
    "provider_error": "The provider returned an unexpected server-side error - check their status page and retry.",
    "unclassified": "No rule matched this error yet - inspect the raw message manually (candidate for a new rule).",
}

# Ordered list of (category, [substrings to match, case-insensitive]).
# Order matters - more specific categories are checked before generic ones.
_RULES = [
    ("authentication_error", ["authentication_error", "invalid x-api-key", "api key is invalid",
                               "invalid_api_key", "is not set", "unauthorized", "401"]),
    ("rate_limit_exceeded", ["rate_limit", "rate limit", "429", "too many requests"]),
    ("model_unavailable", ["no longer available", "model_not_found", "does not exist",
                            "404", "not found"]),
    ("network_timeout", ["timeout", "timed out", "connection error", "connectionerror"]),
    ("unsupported_model", ["unsupported model"]),
    ("invalid_input", ["cannot be empty", "user_prompt is required"]),
    ("empty_response", ["empty response"]),
]


def classify_failure(failed_stage: str, error_message: str) -> Classification:
    """
    Classify a pipeline failure using simple keyword rules.

    Args:
        failed_stage: which stage raised the error (e.g. "llm_call")
        error_message: the raw exception text captured by that stage

    Returns:
        Classification(category, evidence, suggested_fix)
    """
    error_lower = (error_message or "").lower()

    for category, keywords in _RULES:
        for kw in keywords:
            if kw in error_lower:
                # Evidence = the actual matched keyword + a short snippet around it,
                # so a human can see WHY this category was chosen.
                idx = error_lower.find(kw)
                start = max(0, idx - 20)
                end = min(len(error_message), idx + len(kw) + 30)
                evidence = error_message[start:end].strip()
                return Classification(category, evidence, SUGGESTED_FIXES[category])

    # Stage-based fallbacks for errors that don't match a keyword rule
    if failed_stage == "response_parser":
        return Classification("empty_response", error_message[:80], SUGGESTED_FIXES["empty_response"])
    if failed_stage == "evaluator":
        return Classification("evaluation_error", error_message[:80], SUGGESTED_FIXES["evaluation_error"])
    if failed_stage == "llm_call":
        return Classification("provider_error", error_message[:80], SUGGESTED_FIXES["provider_error"])

    return Classification("unclassified", (error_message or "")[:80], SUGGESTED_FIXES["unclassified"])
