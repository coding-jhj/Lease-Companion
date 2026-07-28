"""Cohere SDK를 격리한 rerank provider."""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from lease_companion_ai.evaluation.provider_metrics import (
    ProviderCallMetric,
    extract_cohere_usage,
    metric_recorder_from_env,
)
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.rerank import RerankResult, validate_rerank_results


class CohereRerankProvider:
    model_name = "rerank-v4.0-pro"

    def __init__(
        self,
        *,
        client: Any | None = None,
        metric_sink: Callable[[ProviderCallMetric], None] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        timestamp: Callable[[], str] | None = None,
    ) -> None:
        self._client = client
        self._metric_sink = metric_sink or metric_recorder_from_env()
        self._monotonic = monotonic
        self._timestamp = timestamp or (
            lambda: datetime.now(timezone.utc).isoformat()
        )

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv("COHERE_API_KEY")
        if not api_key:
            raise ProviderError("Cohere rerank provider 설정이 없습니다.")
        import cohere

        self._client = cohere.ClientV2(api_key=api_key)
        return self._client

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int,
    ) -> list[RerankResult]:
        if not query.strip() or any(not document.strip() for document in documents):
            raise ProviderError("빈 검색 질의나 문서는 rerank할 수 없습니다.")
        try:
            started = self._monotonic()
            response = self._get_client().rerank(
                model=self.model_name,
                query=query,
                documents=list(documents),
                top_n=top_n,
            )
            latency_ms = int((self._monotonic() - started) * 1000)
            if self._metric_sink is not None:
                usage = extract_cohere_usage(response)
                self._metric_sink(
                    ProviderCallMetric(
                        timestamp=self._timestamp(),
                        provider="cohere",
                        model=self.model_name,
                        task="rerank",
                        status="success",
                        attempt=1,
                        latency_ms=latency_ms,
                        ttfb_ms=None,
                        input_tokens=usage["input_tokens"],
                        output_tokens=usage["output_tokens"],
                        cached_tokens=0,
                        search_units=usage["search_units"],
                    )
                )
            results = [
                RerankResult(index=result.index, score=float(result.relevance_score))
                for result in response.results
            ]
            return validate_rerank_results(
                results,
                document_count=len(documents),
                top_n=top_n,
            )
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("Cohere rerank 호출에 실패했습니다.") from None
