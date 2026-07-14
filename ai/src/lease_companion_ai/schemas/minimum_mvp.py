"""최소 MVP 파이프라인의 구조화된 입출력 타입."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class DocumentExtraction:
    document_type: str
    fields: dict[str, Any]
    unconfirmed_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvidenceSource:
    source_id: str
    title: str
    institution: str
    summary: str
    source_url: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RuleResult:
    rule_id: str
    rule_name: str
    judgment_id: str | None
    status: str
    urgency: str
    reason: str
    question: str | None
    recommended_actions: list[str]
    evidence_sources: list[EvidenceSource]
    limitations: str
    completed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
