from __future__ import annotations

from collections.abc import Sequence
import chromadb

import lease_companion_ai.rag.service as service_module
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.rerank import RerankResult
from lease_companion_ai.rag.indexing.chroma_index import ChromaVectorIndex
from lease_companion_ai.rag.indexing.chunker import chunk_sections
from lease_companion_ai.rag.models import RetrievalQuery
from lease_companion_ai.rag.service import build_evidence_service


class CountingEmbeddingProvider:
    model_name = "fake-embedding-v1"

    def __init__(self) -> None:
        self.document_calls = 0

    @staticmethod
    def _embed(text: str) -> list[float]:
        return [float(text.count("근저당권")), float(text.count("소유자")), 1.0]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.document_calls += 1
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class FirstDocumentReranker:
    model_name = "fake-rerank-v1"

    def rerank(self, query, documents, *, top_n):
        return [RerankResult(index=0, score=0.9)]


class FailingEmbeddingProvider(CountingEmbeddingProvider):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        raise ProviderError("provider unavailable")


def _chunks(source_metadata):
    return chunk_sections(
        source_metadata,
        [("담보권", "근저당권 채권최고액 확인"), ("소유권", "등기상 소유자 확인")],
    )


def _query():
    return RetrievalQuery(rule_id="R03", rule_name="근저당권 확인", status="확인 필요")


def test_runtime_factory_uses_hybrid_then_rerank(source_metadata):
    service = build_evidence_service(
        _chunks(source_metadata),
        embedding_provider=CountingEmbeddingProvider(),
        rerank_provider=FirstDocumentReranker(),
        chroma_client=chromadb.EphemeralClient(),
        collection_name="runtime_hybrid",
    )

    result = service.search(_query())

    assert result.hits
    assert result.hits[0].retrieval_method == "rerank"
    assert result.provider_fallback_used is False


def test_runtime_factory_reuses_current_index_without_reembedding(source_metadata):
    client = chromadb.EphemeralClient()
    provider = CountingEmbeddingProvider()
    chunks = _chunks(source_metadata)

    build_evidence_service(
        chunks,
        embedding_provider=provider,
        chroma_client=client,
        collection_name="runtime_reuse",
    )
    build_evidence_service(
        chunks,
        embedding_provider=provider,
        chroma_client=client,
        collection_name="runtime_reuse",
    )

    assert provider.document_calls == 1


def test_runtime_factory_rebuilds_stale_index(source_metadata):
    client = chromadb.EphemeralClient()
    provider = CountingEmbeddingProvider()
    chunks = _chunks(source_metadata)
    ChromaVectorIndex(
        provider,
        client=client,
        collection_name="runtime_stale",
        chunking_version="chunk-v1",
    ).index_chunks(chunks)

    service = build_evidence_service(
        chunks,
        embedding_provider=provider,
        chroma_client=client,
        collection_name="runtime_stale",
        chunking_version="chunk-v2",
    )

    assert service.search(_query()).hits
    collection = client.get_collection("runtime_stale")
    assert collection.count() == len(chunks)
    assert collection.metadata["chunking_version"] == "chunk-v2"


def test_runtime_factory_falls_back_to_bm25_when_indexing_fails(source_metadata):
    service = build_evidence_service(
        _chunks(source_metadata),
        embedding_provider=FailingEmbeddingProvider(),
        chroma_client=chromadb.EphemeralClient(),
        collection_name="runtime_fallback",
    )

    result = service.search(_query())

    assert result.hits
    assert all(hit.retrieval_method == "bm25" for hit in result.hits)
    assert result.provider_fallback_used is True


def test_default_factory_selects_configured_hybrid_providers(monkeypatch, source_metadata):
    chunks = _chunks(source_metadata)
    embedding = CountingEmbeddingProvider()
    reranker = FirstDocumentReranker()
    captured = {}
    sentinel = object()

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("COHERE_API_KEY", "fake-key")
    monkeypatch.setattr(service_module, "load_local_official_chunks", lambda: chunks)
    monkeypatch.setattr(service_module, "GeminiEmbeddingProvider", lambda: embedding)
    monkeypatch.setattr(service_module, "CohereRerankProvider", lambda: reranker)

    def fake_builder(_chunks, **kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(service_module, "build_evidence_service", fake_builder)
    service_module.get_default_evidence_service.cache_clear()
    try:
        result = service_module.get_default_evidence_service()
    finally:
        service_module.get_default_evidence_service.cache_clear()

    assert result is sentinel
    assert captured["embedding_provider"] is embedding
    assert captured["rerank_provider"] is reranker
