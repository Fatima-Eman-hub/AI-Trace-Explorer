"""
Response Parser Stage - Stage 5 of the pipeline

Job: Take the raw LLM response and clean/validate it before it goes
     to evaluation and back to the user. Also catches basic quality
     issues early (e.g. empty response, truncated response).
"""

from typing import Any, Dict
from app.stages.base import BaseStage


class ResponseParserStage(BaseStage):
    """
    Parses and validates the raw LLM response.

    Input expected:
        {
            "response_text": "Artificial intelligence is...",
            "stop_reason": "end_turn"
        }

    Output produced:
        {
            "clean_response": "Artificial intelligence is...",
            "response_length_chars": 450,
            "response_length_words": 78,
            "was_truncated": False,
            "is_empty": False
        }
    """

    def __init__(self):
        super().__init__(stage_name="response_parser")

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        response_text = input_data.get("response_text", "") or ""
        stop_reason = input_data.get("stop_reason", "")

        clean_response = response_text.strip()

        was_truncated = stop_reason == "max_tokens"
        is_empty = len(clean_response) == 0

        if is_empty:
            raise ValueError("LLM returned an empty response")

        return {
            "clean_response": clean_response,
            "response_length_chars": len(clean_response),
            "response_length_words": len(clean_response.split()),
            "was_truncated": was_truncated,
            "is_empty": is_empty,
            "stop_reason": stop_reason,
        }
