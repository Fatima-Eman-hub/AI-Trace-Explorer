"""
Tokenizer Stage - Stage 2 of the pipeline

Job: Count tokens in the prompt so we know:
     - How much of the context window we're using
     - Roughly how much this request will cost
     - Whether we're close to the model's limit
"""

from typing import Any, Dict
from app.stages.base import BaseStage


class TokenizerStage(BaseStage):
    """
    Estimates token counts for the prompt.

    Note: This uses a simple word-based approximation (words * 1.3) which
    is close enough for most English text without needing a heavy
    model-specific tokenizer library. Good enough for tracing/estimation
    purposes - real billing will use the token counts returned by the
    actual LLM API response.

    Input expected:
        {
            "formatted_prompt": "...",
            "system_prompt": "...",
            "max_context_tokens": 200000 (optional, from model registry)
        }

    Output produced:
        {
            "estimated_input_tokens": 245,
            "estimated_output_tokens": 150,  (rough guess, refined later)
            "context_window_used_pct": 0.12
        }
    """

    def __init__(self):
        super().__init__(stage_name="tokenizer")

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        formatted_prompt = input_data.get("formatted_prompt", "")
        system_prompt = input_data.get("system_prompt", "") or ""
        max_context_tokens = input_data.get("max_context_tokens", 200000)

        full_text = f"{system_prompt}\n\n{formatted_prompt}"

        input_tokens = self._estimate_tokens(full_text)

        # Rough output estimate - assume response is ~40% of input length
        # (this gets replaced with the REAL count once the LLM responds)
        estimated_output_tokens = max(50, int(input_tokens * 0.4))

        context_used_pct = round(input_tokens / max_context_tokens, 4) if max_context_tokens else 0

        return {
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "context_window_used_pct": context_used_pct,
            "max_context_tokens": max_context_tokens,
        }

    def _estimate_tokens(self, text: str) -> int:
        """
        Simple token estimation: ~1.3 tokens per word for English text.
        This is a widely-used approximation (OpenAI's own docs cite ~0.75
        words per token, i.e. ~1.33 tokens per word).
        """
        if not text.strip():
            return 0
        word_count = len(text.split())
        return int(word_count * 1.3)
