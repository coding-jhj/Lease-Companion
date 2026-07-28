"""RAGAS 0.3.x용 google-genai 직접 LLM adapter."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.outputs import Generation, LLMResult
from ragas.llms import BaseRagasLLM

from lease_companion_ai.providers.gemini_gateway import (
    GeminiCallPolicy,
    GeminiGateway,
    get_gemini_gateway,
)


class GeminiRagasLLM(BaseRagasLLM):
    """instructor 의존 없이 Gemini 응답을 RAGAS LLMResult로 변환한다."""

    def __init__(
        self,
        *,
        client: Any,
        model: str,
        max_output_tokens: int = 2_048,
        gateway: GeminiGateway | None = None,
    ) -> None:
        super().__init__()
        self._client = client
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._gateway = gateway or get_gemini_gateway()

    def generate_text(
        self,
        prompt: Any,
        n: int = 1,
        temperature: float = 0.01,
        stop: list[str] | None = None,
        callbacks: Any = None,
    ) -> LLMResult:
        del callbacks
        from google.genai import types

        generations: list[Generation] = []
        for _ in range(n):
            response = self._gateway.call(
                task="ragas_judge",
                model=self._model,
                policy=GeminiCallPolicy(
                    max_attempts=2,
                    max_total_wait_seconds=30.0,
                ),
                operation=lambda: self._client.models.generate_content(
                    model=self._model,
                    contents=prompt.to_string(),
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=self._max_output_tokens,
                        stop_sequences=stop,
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                ),
            )
            text = getattr(response, "text", None)
            if not text:
                raise ValueError("Gemini RAGAS judge 응답이 비어 있습니다.")
            candidate = (getattr(response, "candidates", None) or [None])[0]
            reason = getattr(candidate, "finish_reason", None)
            finish_reason = str(getattr(reason, "name", reason) or "UNKNOWN")
            generations.append(
                Generation(
                    text=text,
                    generation_info={"finish_reason": finish_reason},
                )
            )
        return LLMResult(generations=[generations])

    async def agenerate_text(
        self,
        prompt: Any,
        n: int = 1,
        temperature: float | None = 0.01,
        stop: list[str] | None = None,
        callbacks: Any = None,
    ) -> LLMResult:
        return await asyncio.to_thread(
            self.generate_text,
            prompt,
            n,
            0.01 if temperature is None else temperature,
            stop,
            callbacks,
        )

    def is_finished(self, response: LLMResult) -> bool:
        unfinished = {"MAX_TOKENS", "SAFETY", "RECITATION", "BLOCKLIST"}
        return all(
            (generation.generation_info or {}).get("finish_reason")
            not in unfinished
            for group in response.generations
            for generation in group
        )
