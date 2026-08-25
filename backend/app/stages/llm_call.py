"""
LLM Call Stage - Stage 4 of the pipeline

Job: Actually call the LLM API (Claude, Groq, or Gemini) and get back a response.
"""

from typing import Any, Dict
from app.stages.base import BaseStage
from app.config import settings

import anthropic
from groq import Groq
import google.generativeai as genai


class LLMCallStage(BaseStage):
    ANTHROPIC_MODEL_IDS = {
        "claude-sonnet": "claude-sonnet-4-6",
        "claude-opus": "claude-opus-4-8",
        "claude-haiku": "claude-haiku-4-5-20251001",
    }

    GROQ_MODEL_IDS = {
        "gpt-oss-120b": "openai/gpt-oss-120b",
        "gpt-oss-20b": "openai/gpt-oss-20b",
    }

    # NOTE: Google renames/retires Gemini model IDs fairly often (they've
    # already done it once during this project - gemini-2.0-flash was
    # retired in favor of gemini-3.6-flash). If this ever 404s again with
    # "model not found" / "no longer available", check the current
    # free-tier model list at https://ai.google.dev/gemini-api/docs/models
    # and update the value below.
    GEMINI_MODEL_IDS = {
        "gemini-flash": "gemini-3.6-flash",
    }

    def __init__(self):
        super().__init__(stage_name="llm_call")
        self._anthropic_client = None
        self._groq_client = None
        self._gemini_configured = False

    def _get_anthropic_client(self) -> anthropic.Anthropic:
        if self._anthropic_client is None:
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")
            self._anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._anthropic_client

    def _get_groq_client(self) -> Groq:
        if self._groq_client is None:
            if not settings.groq_api_key:
                raise ValueError(
                    "GROQ_API_KEY is not set. Add it to your .env file. "
                    "Get a free key at https://console.groq.com"
                )
            self._groq_client = Groq(api_key=settings.groq_api_key)
        return self._groq_client

    def _ensure_gemini_configured(self):
        if not self._gemini_configured:
            if not settings.google_api_key:
                raise ValueError(
                    "GOOGLE_API_KEY is not set. Add it to your .env file. "
                    "Get a free key at https://aistudio.google.com/apikey"
                )
            genai.configure(api_key=settings.google_api_key)
            self._gemini_configured = True

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        provider = input_data.get("provider")
        model_name = input_data.get("model_name")
        formatted_prompt = input_data.get("formatted_prompt", "")
        system_prompt = input_data.get("system_prompt", "") or None
        resolved_parameters = input_data.get("resolved_parameters", {})

        if provider == "anthropic":
            return self._call_anthropic(model_name, formatted_prompt, system_prompt, resolved_parameters)
        elif provider == "groq":
            return self._call_groq(model_name, formatted_prompt, system_prompt, resolved_parameters)
        elif provider == "google":
            return self._call_gemini(model_name, formatted_prompt, system_prompt, resolved_parameters)
        else:
            raise ValueError(f"Provider '{provider}' not yet implemented. Supported: 'anthropic', 'groq', 'google'.")

    def _call_anthropic(self, model_name, prompt, system_prompt, parameters) -> Dict[str, Any]:
        client = self._get_anthropic_client()
        model_id = self.ANTHROPIC_MODEL_IDS.get(model_name, model_name)

        kwargs = {
            "model": model_id,
            "max_tokens": parameters.get("max_tokens", 1024),
            "temperature": parameters.get("temperature", 0.7),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        message = client.messages.create(**kwargs)
        response_text = "".join(block.text for block in message.content if hasattr(block, "text"))

        return {
            "response_text": response_text,
            "actual_input_tokens": message.usage.input_tokens,
            "actual_output_tokens": message.usage.output_tokens,
            "stop_reason": message.stop_reason,
            "provider_model_id": model_id,
        }

    def _call_groq(self, model_name, prompt, system_prompt, parameters) -> Dict[str, Any]:
        client = self._get_groq_client()
        model_id = self.GROQ_MODEL_IDS.get(model_name, model_name)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        completion = client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=parameters.get("temperature", 0.7),
            max_tokens=parameters.get("max_tokens", 1024),
        )

        choice = completion.choices[0]
        return {
            "response_text": choice.message.content,
            "actual_input_tokens": completion.usage.prompt_tokens,
            "actual_output_tokens": completion.usage.completion_tokens,
            "stop_reason": choice.finish_reason,
            "provider_model_id": model_id,
        }

    def _call_gemini(self, model_name, prompt, system_prompt, parameters) -> Dict[str, Any]:
        self._ensure_gemini_configured()
        model_id = self.GEMINI_MODEL_IDS.get(model_name, model_name)

        model_kwargs = {}
        if system_prompt:
            model_kwargs["system_instruction"] = system_prompt

        model = genai.GenerativeModel(model_id, **model_kwargs)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=parameters.get("temperature", 0.7),
                max_output_tokens=parameters.get("max_tokens", 1024),
            ),
        )

        usage = response.usage_metadata
        finish_reason = response.candidates[0].finish_reason.name if response.candidates else "STOP"

        return {
            "response_text": response.text,
            "actual_input_tokens": usage.prompt_token_count,
            "actual_output_tokens": usage.candidates_token_count,
            "stop_reason": finish_reason,
            "provider_model_id": model_id,
        }