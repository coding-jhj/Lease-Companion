"""재정렬 제공자 protocol과 공통 응답 검증."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from lease_companion_ai.providers.errors import ProviderError


@dataclass(frozen=True)
class RerankResult:
    index: int
    score: float


@runtime_checkable
class RerankProvider(Protocol):
    model_name: str

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int,
    ) -> list[RerankResult]: ...


def validate_rerank_results(
    results: Sequence[RerankResult],
    *,
    document_count: int,
    top_n: int,
) -> list[RerankResult]:
    if top_n <= 0 or top_n > document_count:
        raise ProviderError("rerank top_n이 문서 개수 범위를 벗어났습니다.")
    if len(results) > top_n:
        raise ProviderError("rerank 응답이 top_n을 초과했습니다.")
    indexes: set[int] = set()
    validated: list[RerankResult] = []
    for result in results:
        if result.index < 0 or result.index >= document_count or result.index in indexes:
            raise ProviderError("rerank 응답의 문서 인덱스가 유효하지 않습니다.")
        if not math.isfinite(result.score) or result.score < 0:
            raise ProviderError("rerank 점수는 0 이상의 유한한 값이어야 합니다.")
        indexes.add(result.index)
        validated.append(result)
    return validated
