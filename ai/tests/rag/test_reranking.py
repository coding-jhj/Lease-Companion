from __future__ import annotations

from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.rerank import RerankResult
from lease_companion_ai.rag.indexing.chunker import chunk_sections
from lease_companion_ai.rag.models import RetrievalHit, RetrievalQuery
from lease_companion_ai.rag.reranking.service import RerankingService


class ReverseRerankProvider:
    model_name = "fake-rerank-v1"

    def rerank(self, query, documents, *, top_n):
        return [RerankResult(index=len(documents) - 1, score=0.9)]


class FailingRerankProvider:
    model_name = "fake-rerank-v1"

    def rerank(self, query, documents, *, top_n):
        raise ProviderError("민감 입력 없는 provider 실패")


def _query():
    return RetrievalQuery(rule_id="R03", rule_name="근저당권 확인", status="확인 필요")


def _hits(source_metadata):
    chunks = chunk_sections(source_metadata, [("가", "첫 근거"), ("나", "둘째 근거")])
    return [
        RetrievalHit(chunk=chunk, score=1.0 / rank, rank=rank, retrieval_method="hybrid")
        for rank, chunk in enumerate(chunks, start=1)
    ]


def test_reranking_returns_provider_order(source_metadata):
    hits = RerankingService(ReverseRerankProvider()).rerank(_query(), _hits(source_metadata))

    assert len(hits) == 1
    assert hits[0].chunk.section == "나"
    assert hits[0].retrieval_method == "rerank"


def test_reranking_failure_preserves_hybrid_order(source_metadata):
    original = _hits(source_metadata)
    hits = RerankingService(FailingRerankProvider()).rerank(_query(), original, top_n=1)

    assert hits == original[:1]
    assert hits[0].retrieval_method == "hybrid"
