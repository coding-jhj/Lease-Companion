"""파이프라인 판정과 분리된 routing 실행 기록 계약."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class ProcessingStage(str, Enum):
    EXTRACTION = "extraction"
    EMBEDDING = "embedding"
    RERANK = "rerank"


class RouteTarget(str, Enum):
    GEMINI_EXTRACTION = "gemini_3_5_flash"
    LOCAL_EXTRACTION = "local_regex"
    GEMINI_EMBEDDING = "gemini_embedding_001"
    BM25 = "bm25"
    COHERE_RERANK = "cohere_rerank_v4_pro"
    HYBRID_RANK = "hybrid_rank"


class RoutingFailureReason(str, Enum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_ERROR = "provider_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    RESPONSE_VALIDATION_FAILED = "response_validation_failed"


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    stage: ProcessingStage
    primary: RouteTarget
    selected: RouteTarget
    primary_available: bool
    fallback_used: bool
    failure_reason: RoutingFailureReason | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
