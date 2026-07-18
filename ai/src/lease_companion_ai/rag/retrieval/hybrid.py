"""BM25·vector 순위를 결정적으로 결합하는 RRF 검색."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.rag.models import EvidenceQuery, RetrievalHit
from lease_companion_ai.rag.retrieval.bm25 import BM25Index


class VectorSearcher(Protocol):
    def search(
        self,
        query: EvidenceQuery | str,
        *,
        top_k: int = 20,
    ) -> list[RetrievalHit]: ...


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[RetrievalHit]],
    *,
    top_k: int = 20,
    rrf_k: int = 60,
) -> list[RetrievalHit]:
    if top_k <= 0 or rrf_k <= 0:
        raise ValueError("top_k와 rrf_k는 양수여야 합니다.")
    scores: dict[str, float] = {}
    chunks = {}
    for ranking in rankings:
        seen: set[str] = set()
        for position, hit in enumerate(ranking, start=1):
            chunk_id = hit.chunk.chunk_id
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            chunks[chunk_id] = hit.chunk
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + position)
    ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))[:top_k]
    return [
        RetrievalHit(
            chunk=chunks[chunk_id],
            score=scores[chunk_id],
            rank=rank,
            retrieval_method="hybrid",
        )
        for rank, chunk_id in enumerate(ordered, start=1)
    ]


class HybridRetriever:
    def __init__(self, bm25: BM25Index, vector: VectorSearcher) -> None:
        self._bm25 = bm25
        self._vector = vector

    def search(
        self,
        query: EvidenceQuery | str,
        *,
        top_k: int = 20,
    ) -> list[RetrievalHit]:
        bm25_hits = self._bm25.search(query, top_k=top_k)
        try:
            vector_hits = self._vector.search(query, top_k=top_k)
        except ProviderError:
            return bm25_hits
        return reciprocal_rank_fusion([bm25_hits, vector_hits], top_k=top_k)
