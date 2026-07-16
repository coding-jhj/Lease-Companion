"""Google GenAI SDK를 격리한 Gemini embedding provider."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from lease_companion_ai.providers.embeddings import validate_embeddings
from lease_companion_ai.providers.errors import ProviderError


class GeminiEmbeddingProvider:
    model_name = "gemini-embedding-001"

    def __init__(
        self,
        *,
        client: Any | None = None,
        output_dimensionality: int = 768,
    ) -> None:
        if output_dimensionality <= 0:
            raise ValueError("output_dimensionality는 양수여야 합니다.")
        self._client = client
        self._output_dimensionality = output_dimensionality

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ProviderError("Gemini embedding provider 설정이 없습니다.")
        from google import genai

        self._client = genai.Client(api_key=api_key)
        return self._client

    def _embed(self, texts: Sequence[str], *, task_type: str) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ProviderError("빈 텍스트는 embedding할 수 없습니다.")
        try:
            from google.genai import types

            response = self._get_client().models.embed_content(
                model=self.model_name,
                contents=list(texts),
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self._output_dimensionality,
                ),
            )
            raw_embeddings = response.embeddings or []
            embeddings = [embedding.values or [] for embedding in raw_embeddings]
            return validate_embeddings(embeddings, expected_count=len(texts))
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("Gemini embedding 호출에 실패했습니다.") from None

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], task_type="RETRIEVAL_QUERY")[0]
