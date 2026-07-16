"""공식자료 후보만 받아 Cohere 호환 provider로 재정렬한다."""

from __future__ import annotations

from collections.abc import Sequence

from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.rerank import RerankProvider, validate_rerank_results
from lease_companion_ai.rag.models import RetrievalHit, RetrievalQuery


class RerankingService:
    def __init__(self, provider: RerankProvider) -> None:
        self._provider = provider

    def rerank(
        self,
        query: RetrievalQuery,
        hits: Sequence[RetrievalHit],
        *,
        top_n: int = 5,
    ) -> list[RetrievalHit]:
        if top_n <= 0:
            raise ValueError("top_n은 양수여야 합니다.")
        official_hits = [
            hit
            for hit in hits
            if hit.chunk.metadata.source_status == "official_verified"
            and hit.chunk.metadata.source_url.startswith("https://")
            and bool(hit.chunk.metadata.institution.strip())
        ]
        if not official_hits:
            return []
        result_count = min(top_n, len(official_hits))
        try:
            results = self._provider.rerank(
                query.to_search_text(),
                [hit.chunk.text for hit in official_hits],
                top_n=result_count,
            )
            validated = validate_rerank_results(
                results,
                document_count=len(official_hits),
                top_n=result_count,
            )
        except ProviderError:
            return list(official_hits[:result_count])
        if not validated:
            return list(official_hits[:result_count])
        return [
            RetrievalHit(
                chunk=official_hits[result.index].chunk,
                score=result.score,
                rank=rank,
                retrieval_method="rerank",
            )
            for rank, result in enumerate(validated, start=1)
        ]
