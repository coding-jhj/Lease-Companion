"""규칙 판정과 분리해 보관하는 사용자 안내 생성 내부 계약."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lease_companion_ai.schemas.unified import (
    GenerationMethod,
    GuidanceActionItem,
    GenerationResult,
    JudgmentGuidance,
    RuleGuidance,
    SpecialClauseGuidance,
    StageGuidance,
)

__all__ = [
    "GeneratedGuidanceDraft",
    "GenerationMethod",
    "GenerationResult",
    "GuidanceActionItem",
    "JudgmentGuidance",
    "RuleGuidance",
    "SpecialClauseGuidance",
    "StageGuidance",
]


def _validate_unique_non_empty(
    values: tuple[str, ...], *, label: str
) -> tuple[str, ...]:
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} 목록에는 빈 문자열을 넣을 수 없습니다.")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} 목록에는 중복 값을 넣을 수 없습니다.")
    return values


class GeneratedGuidanceDraft(BaseModel):
    """생성 provider가 반환하는 규칙 1개 단위 구조화 초안."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    explanation: str = Field(min_length=1)
    questions: tuple[str, ...] = ()
    request_templates: tuple[str, ...] = ()
    signing_checklist: tuple[str, ...] = ()
    post_contract_actions: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "questions", "request_templates", "signing_checklist", "post_contract_actions", "source_ids"
    )
    @classmethod
    def _unique_non_empty(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_unique_non_empty(values, label="생성")
