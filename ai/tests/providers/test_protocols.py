from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from lease_companion_ai.providers.embeddings import EmbeddingProvider, validate_embeddings
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.rerank import (
    RerankProvider,
    RerankResult,
    validate_rerank_results,
)


class FakeEmbeddingProvider:
    model_name = "fake-embedding-v1"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]


class FakeRerankProvider:
    model_name = "fake-rerank-v1"

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int,
    ) -> list[RerankResult]:
        ranked = sorted(
            enumerate(documents),
            key=lambda item: (-int(query in item[1]), item[0]),
        )[:top_n]
        return [RerankResult(index=index, score=float(query in text)) for index, text in ranked]


def test_fake_providers_satisfy_protocols():
    assert isinstance(FakeEmbeddingProvider(), EmbeddingProvider)
    assert isinstance(FakeRerankProvider(), RerankProvider)


def test_embedding_validation_accepts_consistent_vectors():
    provider = FakeEmbeddingProvider()
    embeddings = provider.embed_documents(["하나", "둘"])
    assert validate_embeddings(embeddings, expected_count=2) == embeddings


@pytest.mark.parametrize(
    "embeddings",
    [
        [[1.0]],
        [[1.0], [1.0, 2.0]],
        [[1.0], [math.inf]],
    ],
)
def test_embedding_validation_rejects_invalid_response(embeddings):
    with pytest.raises(ProviderError):
        validate_embeddings(embeddings, expected_count=2)


def test_rerank_validation_accepts_fake_response():
    provider = FakeRerankProvider()
    results = provider.rerank("근거", ["공식 근거", "다른 문서"], top_n=2)
    assert validate_rerank_results(results, document_count=2, top_n=2) == results


def test_rerank_validation_rejects_duplicate_index():
    with pytest.raises(ProviderError):
        validate_rerank_results(
            [RerankResult(0, 1.0), RerankResult(0, 0.5)],
            document_count=2,
            top_n=2,
        )
