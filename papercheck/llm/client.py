"""Anthropic API wrapper with retry, cost tracking, and structured output parsing."""

from __future__ import annotations

import json
import logging
from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from papercheck.config import PipelineConfig
from papercheck.llm.prompts import get_prompt

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Approximate pricing per 1M tokens (Sonnet)
_INPUT_COST_PER_M = 3.0
_OUTPUT_COST_PER_M = 15.0


class LLMClient:
    """Thin wrapper around Anthropic SDK with cost tracking and structured output."""

    def __init__(self, config: PipelineConfig):
        self._config = config
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self._model = config.anthropic_model
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    async def query(
        self,
        prompt_name: str,
        variables: dict,
        output_schema: type[T] | None = None,
    ) -> T | dict:
        """Send a prompt to the LLM and parse the response.

        Looks up the prompt template by name, fills variables, calls the API,
        and parses the response into the output schema. Retries once on parse failure.
        """
        spec = get_prompt(prompt_name)
        schema = output_schema or spec.output_schema

        user_message = spec.user_template.format(**variables)

        # Try up to 2 times (initial + 1 retry on parse failure)
        last_error = None
        for attempt in range(2):
            response = self._call_api(spec.system, user_message, spec.temperature, spec.max_tokens)
            try:
                return self._parse_response(response, schema)
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                logger.warning(
                    "LLM response parse failed (attempt %d): %s", attempt + 1, e
                )
                # Add a hint to the user message for retry
                user_message = (
                    f"{user_message}\n\nIMPORTANT: Your previous response was not valid JSON. "
                    f"Please respond with ONLY valid JSON, no markdown fences or extra text."
                )

        raise LLMParseError(
            f"Failed to parse LLM response after 2 attempts: {last_error}"
        )

    def _call_api(
        self, system: str, user_message: str, temperature: float, max_tokens: int
    ) -> str:
        """Make a synchronous API call and track tokens."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens
        return response.content[0].text

    def _parse_response(self, text: str, schema: type[T]) -> T:
        """Parse LLM text response into a Pydantic model."""
        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last line (fences)
            lines = [l for l in lines[1:] if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        data = json.loads(cleaned)
        return schema.model_validate(data)

    def get_cost_summary(self) -> dict:
        """Return cumulative token usage and estimated cost."""
        input_cost = (self._total_input_tokens / 1_000_000) * _INPUT_COST_PER_M
        output_cost = (self._total_output_tokens / 1_000_000) * _OUTPUT_COST_PER_M
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "estimated_cost_usd": round(input_cost + output_cost, 4),
        }


class LLMParseError(Exception):
    """Raised when LLM response cannot be parsed into the expected schema."""
