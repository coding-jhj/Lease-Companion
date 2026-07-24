from __future__ import annotations

from types import SimpleNamespace

import pytest

from lease_companion_ai.providers.cohere_rerank import CohereRerankProvider
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.gemini_embeddings import GeminiEmbeddingProvider


class FakeGeminiModels:
    def __init__(self) -> None:
        self.calls = []

    def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        embeddings = [SimpleNamespace(values=[float(index), 1.0]) for index, _ in enumerate(kwargs["contents"])]
        return SimpleNamespace(embeddings=embeddings)


class FakeCohereClient:
    def __init__(self) -> None:
        self.calls = []

    def rerank(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            results=[SimpleNamespace(index=1, relevance_score=0.9)]
        )


def test_gemini_adapter_uses_fixed_model_and_task_types():
    models = FakeGeminiModels()
    provider = GeminiEmbeddingProvider(client=SimpleNamespace(models=models))

    assert len(provider.embed_documents(["문서 하나", "문서 둘"])) == 2
    assert provider.embed_query("비식별 질의") == [0.0, 1.0]
    assert [call["model"] for call in models.calls] == ["gemini-embedding-001"] * 2
    assert models.calls[0]["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert models.calls[1]["config"].task_type == "RETRIEVAL_QUERY"


def test_gemini_adapter_does_not_require_key_until_real_call(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="설정"):
        GeminiEmbeddingProvider().embed_query("비식별 질의")


def test_gemini_adapter_splits_documents_into_request_batches():
    """코퍼스 39건을 한 요청에 보내면 무료 티어에서 429가 난다(2026-07-23 실측)."""
    models = FakeGeminiModels()
    provider = GeminiEmbeddingProvider(
        client=SimpleNamespace(models=models), batch_size=3
    )

    embeddings = provider.embed_documents([f"문서 {index}" for index in range(7)])

    assert len(embeddings) == 7
    assert [len(call["contents"]) for call in models.calls] == [3, 3, 1]


def test_gemini_embedding_batch_size_can_be_configured(monkeypatch):
    monkeypatch.setenv("GEMINI_EMBEDDING_BATCH_SIZE", "2")
    models = FakeGeminiModels()
    provider = GeminiEmbeddingProvider(client=SimpleNamespace(models=models))

    provider.embed_documents([f"문서 {index}" for index in range(5)])

    assert [len(call["contents"]) for call in models.calls] == [2, 2, 1]


def test_gemini_embedding_rejects_non_positive_batch_size():
    with pytest.raises(ValueError, match="batch_size"):
        GeminiEmbeddingProvider(batch_size=-1)


def test_gemini_embedding_rejects_non_positive_timeout():
    with pytest.raises(ValueError, match="timeout_seconds"):
        GeminiEmbeddingProvider(timeout_seconds=0)


def test_cohere_adapter_uses_fixed_model():
    client = FakeCohereClient()
    results = CohereRerankProvider(client=client).rerank(
        "R03 근저당권 확인 필요",
        ["첫 문서", "둘째 문서"],
        top_n=1,
    )

    assert [(result.index, result.score) for result in results] == [(1, 0.9)]
    assert client.calls[0]["model"] == "rerank-v4.0-pro"


def test_cohere_adapter_does_not_require_key_until_real_call(monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="설정"):
        CohereRerankProvider().rerank("질의", ["문서"], top_n=1)
