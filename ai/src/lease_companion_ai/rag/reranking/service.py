"""공식자료 후보만 받아 Cohere 호환 provider로 재정렬한다."""

from __future__ import annotations

from collections.abc import Sequence

from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderResponseValidationError,
)
from lease_companion_ai.providers.rerank import RerankProvider, validate_rerank_results
from lease_companion_ai.rag.models import EvidenceQuery, RetrievalHit
from lease_companion_ai.routing.models import ProcessingStage, RouteTarget
from lease_companion_ai.routing.service import RoutedExecution, RoutingService


class RerankingService:
    def __init__(self, provider: RerankProvider) -> None:
        self._provider = provider

    def rerank(
        self,
        query: EvidenceQuery,
        hits: Sequence[RetrievalHit],
        *,
        top_n: int = 5,
    ) -> list[RetrievalHit]:
        return self.rerank_routed(query, hits, top_n=top_n).value

    def rerank_routed(
        self,
        query: EvidenceQuery,
        hits: Sequence[RetrievalHit],
        *,
        top_n: int = 5,
    ) -> RoutedExecution[list[RetrievalHit]]:
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
            return RoutingService().execute(
                stage=ProcessingStage.RERANK,
                primary_target=RouteTarget.COHERE_RERANK,
                fallback_target=RouteTarget.HYBRID_RANK,
                primary=lambda: [],
                fallback=lambda: [],
            )
        result_count = min(top_n, len(official_hits))

        def provider_rerank() -> list[RetrievalHit]:
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
            if not validated:
                raise ProviderResponseValidationError(
                    "rerank 응답이 비어 있습니다."
                )
            return [
                RetrievalHit(
                    chunk=official_hits[result.index].chunk,
                    score=result.score,
                    rank=rank,
                    retrieval_method="rerank",
                )
                for rank, result in enumerate(validated, start=1)
            ]

        return RoutingService().execute(
            stage=ProcessingStage.RERANK,
            primary_target=RouteTarget.COHERE_RERANK,
            fallback_target=RouteTarget.HYBRID_RANK,
            primary=provider_rerank,
            fallback=lambda: list(official_hits[:result_count]),
            handled_errors=(ProviderError,),
        )
