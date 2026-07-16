"""Cohere SDK를 격리한 rerank provider."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.rerank import RerankResult, validate_rerank_results


class CohereRerankProvider:
    model_name = "rerank-v4.0-pro"

    def __init__(self, *, client: Any | None = None) -> None:
        self._client = client

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
            response = self._get_client().rerank(
                model=self.model_name,
                query=query,
                documents=list(documents),
                top_n=top_n,
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
