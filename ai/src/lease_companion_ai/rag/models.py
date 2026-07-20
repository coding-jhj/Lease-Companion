"""RAG 내부 검색 계약. Backend·Frontend 공개 canonical schema와 분리한다."""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lease_companion_ai.schemas.unified import RuleStatus


_SOURCE_ID_PATTERN = r"^SRC-[A-Z0-9-]+$"
_CHUNK_ID_PATTERN = r"^SRC-[A-Z0-9-]+:[0-9a-f]{64}$"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SourceId = Annotated[str, Field(pattern=_SOURCE_ID_PATTERN)]


class RagSourceMetadata(BaseModel):
    """검색 코퍼스에 들어갈 공식자료 메타데이터."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=_SOURCE_ID_PATTERN)
    source_status: Literal["official_verified"] = "official_verified"
    document_title: str = Field(min_length=1)
    institution: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    article_or_section: str = Field(min_length=1)
    effective_date: str | None = None
    source_url: str
    collected_date: date
    source_sha256: str
    usage_terms: str = Field(min_length=1)

    @field_validator("source_url")
    @classmethod
    def _official_https_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("공식자료 source_url은 https URL이어야 합니다.")
        return value

    @field_validator("source_sha256")
    @classmethod
    def _sha256_hex(cls, value: str) -> str:
        normalized = value.lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("source_sha256은 64자리 SHA-256 hex여야 합니다.")
        return normalized


class RagChunk(BaseModel):
    """결정적 청킹으로 생성된 검색 단위."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str = Field(pattern=_CHUNK_ID_PATTERN)
    metadata: RagSourceMetadata
    section: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1)


class RetrievalQuery(BaseModel):
    """개인정보를 제외한 규칙 단위 검색 질의."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(pattern=r"^R\d{2}$")
    rule_name: str = Field(min_length=1)
    status: RuleStatus
    allowed_source_ids: tuple[SourceId, ...] = ()
    evidence_search_context: str | None = Field(default=None, max_length=2000)
    deidentified_clause_context: str | None = Field(default=None, max_length=2000)

    @field_validator("allowed_source_ids")
    @classmethod
    def _unique_sources(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("R 검색 허용 source ID는 중복될 수 없습니다.")
        return values

    def to_search_text(self) -> str:
        parts = [self.rule_id, self.rule_name, self.status.value]
        if self.evidence_search_context:
            parts.append(self.evidence_search_context)
        if self.deidentified_clause_context:
            parts.append(self.deidentified_clause_context)
        return " ".join(parts)


class JudgmentRetrievalQuery(BaseModel):
    """판정별 허용 공식자료 범위를 포함한 J01~J12 검색 질의."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    judgment_id: str = Field(pattern=r"^J(?:0[1-9]|1[0-2])$")
    judgment_name: str = Field(min_length=1)
    status: RuleStatus
    allowed_source_ids: tuple[SourceId, ...] = Field(min_length=1)
    evidence_search_context: str | None = Field(default=None, max_length=2000)
    deidentified_clause_context: str | None = Field(default=None, max_length=2000)

    @field_validator("allowed_source_ids")
    @classmethod
    def _unique_sources(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("J 검색 허용 source ID는 중복될 수 없습니다.")
        return values

    def to_search_text(self) -> str:
        parts = [self.judgment_id, self.judgment_name, self.status.value]
        if self.evidence_search_context:
            parts.append(self.evidence_search_context)
        if self.deidentified_clause_context:
            parts.append(self.deidentified_clause_context)
        return " ".join(parts)


EvidenceQuery = RetrievalQuery | JudgmentRetrievalQuery


def query_to_search_text(query: EvidenceQuery | str) -> str:
    return query if isinstance(query, str) else query.to_search_text()


class RetrievalHit(BaseModel):
    """검색 단계가 반환하는 순위화된 청크."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk: RagChunk
    score: float = Field(ge=0)
    rank: int = Field(ge=1)
    retrieval_method: Literal["bm25", "vector", "hybrid", "rerank"]

    @field_validator("score")
    @classmethod
    def _finite_score(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("검색 점수는 유한한 값이어야 합니다.")
        return value
