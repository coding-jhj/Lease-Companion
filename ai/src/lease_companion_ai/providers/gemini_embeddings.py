"""Google GenAI SDK를 격리한 Gemini embedding provider."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from typing import Any

from lease_companion_ai.providers.embeddings import validate_embeddings
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.gemini_gateway import (
    GeminiCallPolicy,
    GeminiGateway,
    get_gemini_gateway,
)


logger = logging.getLogger(__name__)

# 코퍼스 39건을 한 요청에 보내면 무료 티어에서 429가 난다(2026-07-23 실측: 1건은 성공).
# 한 요청의 contents 수를 나눠 보내면 같은 코퍼스를 정상 인덱싱할 수 있다.
_DEFAULT_BATCH_SIZE = 8


class GeminiEmbeddingProvider:
    model_name = "gemini-embedding-001"

    def __init__(
        self,
        *,
        client: Any | None = None,
        output_dimensionality: int = 768,
        timeout_seconds: float = 30.0,
        batch_size: int | None = None,
        gateway: GeminiGateway | None = None,
    ) -> None:
        if output_dimensionality <= 0:
            raise ValueError("output_dimensionality는 양수여야 합니다.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 양수여야 합니다.")
        resolved_batch = batch_size or int(
            os.getenv("GEMINI_EMBEDDING_BATCH_SIZE", _DEFAULT_BATCH_SIZE)
        )
        if resolved_batch <= 0:
            raise ValueError("batch_size는 양수여야 합니다.")
        self._client = client
        self._output_dimensionality = output_dimensionality
        self._timeout_seconds = timeout_seconds
        self._batch_size = resolved_batch
        # 다른 Gemini 호출과 달리 embedding만 Gateway 밖에 있어 재시도·간격 제어가
        # 없었다. 코퍼스 인덱싱은 연속 요청이라 429에 특히 취약하다(2026-07-23 실측).
        self._gateway = gateway or get_gemini_gateway()

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ProviderError("Gemini embedding provider 설정이 없습니다.")
        from google import genai
        from google.genai import types

        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(self._timeout_seconds * 1_000)),
        )
        return self._client

    def _embed(self, texts: Sequence[str], *, task_type: str) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ProviderError("빈 텍스트는 embedding할 수 없습니다.")
        items = list(texts)
        if len(items) <= self._batch_size:
            return self._embed_once(items, task_type=task_type)
        embeddings: list[list[float]] = []
        for start in range(0, len(items), self._batch_size):
            embeddings.extend(
                self._embed_once(
                    items[start : start + self._batch_size], task_type=task_type
                )
            )
        return validate_embeddings(embeddings, expected_count=len(items))

    def _embed_once(self, texts: list[str], *, task_type: str) -> list[list[float]]:
        try:
            from google.genai import types

            response = self._gateway.call(
                task="embedding",
                model=self.model_name,
                policy=GeminiCallPolicy(max_attempts=3, max_total_wait_seconds=30.0),
                operation=lambda: self._get_client().models.embed_content(
                    model=self.model_name,
                    contents=list(texts),
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self._output_dimensionality,
                    ),
                ),
            )
            raw_embeddings = response.embeddings or []
            embeddings = [embedding.values or [] for embedding in raw_embeddings]
            return validate_embeddings(embeddings, expected_count=len(texts))
        except ProviderError:
            raise
        except Exception as exc:
            # 원문에는 코퍼스 텍스트가 섞일 수 있어 그대로 남기지 않는다.
            # 상태 코드와 예외 타입만 남겨도 429·인증·스키마 오류가 구분된다.
            logger.warning(
                "Gemini embedding 실패 건수=%d type=%s status=%s",
                len(texts),
                type(exc).__name__,
                getattr(exc, "code", None) or getattr(exc, "status_code", None),
            )
            raise ProviderError("Gemini embedding 호출에 실패했습니다.") from None

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], task_type="RETRIEVAL_QUERY")[0]
