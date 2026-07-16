from __future__ import annotations

from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.rag.indexing.chunker import chunk_sections
from lease_companion_ai.rag.models import RetrievalHit
from lease_companion_ai.rag.retrieval.bm25 import BM25Index
from lease_companion_ai.rag.retrieval.hybrid import HybridRetriever, reciprocal_rank_fusion


def _hits(source_metadata):
    chunks = chunk_sections(source_metadata, [("가", "근저당권 확인"), ("나", "소유자 확인")])
    return chunks, [
        RetrievalHit(chunk=chunks[0], score=2.0, rank=1, retrieval_method="bm25"),
        RetrievalHit(chunk=chunks[1], score=1.0, rank=2, retrieval_method="bm25"),
    ]


def test_rrf_is_deterministic_and_deduplicates(source_metadata):
    chunks, lexical = _hits(source_metadata)
    vector = [
        RetrievalHit(chunk=chunks[1], score=0.9, rank=1, retrieval_method="vector"),
        RetrievalHit(chunk=chunks[0], score=0.8, rank=2, retrieval_method="vector"),
    ]

    first = reciprocal_rank_fusion([lexical, vector])
    second = reciprocal_rank_fusion([lexical, vector])

    assert first == second
    assert len(first) == 2
    assert [hit.chunk.chunk_id for hit in first] == sorted(chunk.chunk_id for chunk in chunks)
    assert all(hit.retrieval_method == "hybrid" for hit in first)


class FailingVectorSearcher:
    def search(self, query, *, top_k=20):
        raise ProviderError("외부 입력을 포함하지 않는 실패")


def test_hybrid_retriever_falls_back_to_bm25(source_metadata):
    chunks, _ = _hits(source_metadata)
    retriever = HybridRetriever(BM25Index(chunks), FailingVectorSearcher())

    hits = retriever.search("근저당권")

    assert hits[0].retrieval_method == "bm25"
    assert hits[0].chunk.section == "가"
