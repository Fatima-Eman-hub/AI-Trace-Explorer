"""
LLM Gateway Stage - Stage 3 of the pipeline

Job: Decide WHICH provider/model to route this request to, and prepare
     the provider-specific configuration.
"""

from typing import Any, Dict
from app.stages.base import BaseStage


# Registry of known providers per model prefix.
# Supported: Anthropic (Claude), Groq (free gpt-oss models), Google (Gemini free tier).
# OpenAI removed - never had a genuinely free tier worth building against.
MODEL_PROVIDER_MAP = {
    "claude-sonnet": "anthropic",
    "claude-opus": "anthropic",
    "claude-haiku": "anthropic",
    "gpt-oss-120b": "groq",
    "gpt-oss-20b": "groq",
    "gemini-flash": "google",
}


class LLMGatewayStage(BaseStage):
    def __init__(self):
        super().__init__(stage_name="llm_gateway")

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        model_name = input_data.get("model_name", "")
        model_parameters = input_data.get("model_parameters", {}) or {}

        if not model_name:
            raise ValueError("model_name is required")

        provider = self._resolve_provider(model_name)
        if provider is None:
            raise ValueError(f"Unsupported model: '{model_name}'. "
                              f"Supported: {list(MODEL_PROVIDER_MAP.keys())}")

        resolved_parameters = {
            "temperature": model_parameters.get("temperature", 0.7),
            "max_tokens": model_parameters.get("max_tokens", 1024),
        }

        return {
            "provider": provider,
            "model_name": model_name,
            "resolved_parameters": resolved_parameters,
        }

    def _resolve_provider(self, model_name: str) -> str:
        model_lower = model_name.lower()
        for known_model, provider in MODEL_PROVIDER_MAP.items():
            if model_lower.startswith(known_model):
                return provider
        return None
