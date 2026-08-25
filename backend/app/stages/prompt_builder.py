"""
Prompt Builder Stage - Stage 1 of the pipeline

Job: Take the raw user_prompt + system_prompt + few_shot_examples
     and combine them into a properly formatted prompt ready for the LLM.
"""

from typing import Any, Dict
from app.stages.base import BaseStage


class PromptBuilderStage(BaseStage):
    """
    Formats the final prompt that will be sent to the LLM.

    Input expected:
        {
            "user_prompt": "What is AI?",
            "system_prompt": "You are a helpful assistant" (optional),
            "few_shot_examples": [{"input": "...", "output": "..."}] (optional)
        }

    Output produced:
        {
            "formatted_prompt": "Full text ready for the model",
            "system_prompt": "...",
            "num_few_shot_examples": 2
        }
    """

    def __init__(self):
        super().__init__(stage_name="prompt_builder")

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        user_prompt = input_data.get("user_prompt", "").strip()
        system_prompt = input_data.get("system_prompt", "") or ""
        few_shot_examples = input_data.get("few_shot_examples", []) or []

        if not user_prompt:
            raise ValueError("user_prompt cannot be empty")

        # Build few-shot examples section
        few_shot_text = ""
        if few_shot_examples:
            examples_parts = []
            for example in few_shot_examples:
                ex_input = example.get("input", "")
                ex_output = example.get("output", "")
                examples_parts.append(f"Q: {ex_input}\nA: {ex_output}")
            few_shot_text = "\n\n".join(examples_parts) + "\n\n"

        # Combine everything into final prompt
        formatted_prompt = f"{few_shot_text}{user_prompt}"

        return {
            "formatted_prompt": formatted_prompt,
            "system_prompt": system_prompt,
            "num_few_shot_examples": len(few_shot_examples),
            "prompt_length_chars": len(formatted_prompt),
        }
