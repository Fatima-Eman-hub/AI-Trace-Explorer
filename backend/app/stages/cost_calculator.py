"""
Cost Calculator Stage - Stage 7 of the pipeline
"""

from typing import Any, Dict
from app.stages.base import BaseStage


MODEL_PRICING = {
    "claude-sonnet": {"input": 0.003, "output": 0.015},
    "claude-opus":   {"input": 0.015, "output": 0.075},
    "claude-haiku":  {"input": 0.0008, "output": 0.004},
    "gpt-oss-120b": {"input": 0.0, "output": 0.0},
    "gpt-oss-20b":  {"input": 0.0, "output": 0.0},
    "gemini-flash": {"input": 0.0, "output": 0.0},
}


class CostCalculatorStage(BaseStage):
    def __init__(self):
        super().__init__(stage_name="cost_calculator")

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        model_name = input_data.get("model_name", "")
        input_tokens = input_data.get("actual_input_tokens", 0)
        output_tokens = input_data.get("actual_output_tokens", 0)

        pricing = self._get_pricing(model_name)
        input_cost = round((input_tokens / 1000) * pricing["input"], 6)
        output_cost = round((output_tokens / 1000) * pricing["output"], 6)

        return {
            "input_cost_usd": input_cost,
            "output_cost_usd": output_cost,
            "total_cost_usd": round(input_cost + output_cost, 6),
        }

    def _get_pricing(self, model_name: str) -> Dict[str, float]:
        model_lower = model_name.lower()
        for known_model, pricing in MODEL_PRICING.items():
            if model_lower.startswith(known_model):
                return pricing
        return MODEL_PRICING["claude-sonnet"]
