"""임베딩 제공자 protocol과 공통 응답 검증."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from lease_companion_ai.providers.errors import ProviderResponseValidationError


@runtime_checkable
class EmbeddingProvider(Protocol):
    model_name: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def validate_embeddings(
    embeddings: Sequence[Sequence[float]],
    *,
    expected_count: int,
) -> list[list[float]]:
    if len(embeddings) != expected_count:
        raise ProviderResponseValidationError(
            "임베딩 응답 개수가 요청 개수와 다릅니다."
        )
    if not embeddings:
        return []
    dimension = len(embeddings[0])
    if dimension == 0:
        raise ProviderResponseValidationError("임베딩 차원은 1 이상이어야 합니다.")
    validated: list[list[float]] = []
    for embedding in embeddings:
        values = [float(value) for value in embedding]
        if len(values) != dimension or not all(math.isfinite(value) for value in values):
            raise ProviderResponseValidationError(
                "임베딩 응답의 차원 또는 값이 유효하지 않습니다."
            )
        validated.append(values)
    return validated
