"""규칙 판정과 분리해 보관하는 사용자 안내 생성 내부 계약."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _validate_unique_non_empty(
    values: tuple[str, ...], *, label: str
) -> tuple[str, ...]:
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} 목록에는 빈 문자열을 넣을 수 없습니다.")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} 목록에는 중복 값을 넣을 수 없습니다.")
    return values


class GenerationMethod(str, Enum):
    PROVIDER = "provider"
    TEMPLATE_FALLBACK = "template_fallback"


class GeneratedGuidanceDraft(BaseModel):
    """생성 provider가 반환하는 규칙 1개 단위 구조화 초안."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    explanation: str = Field(min_length=1)
    questions: tuple[str, ...] = ()
    signing_checklist: tuple[str, ...] = ()
    post_contract_actions: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "questions", "signing_checklist", "post_contract_actions", "source_ids"
    )
    @classmethod
    def _unique_non_empty(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_unique_non_empty(values, label="생성")


class RuleGuidance(BaseModel):
    """검증 또는 fallback을 마친 규칙 1개의 사용자 안내."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(pattern=r"^R\d{2}$")
    explanation: str = Field(min_length=1)
    questions: tuple[str, ...] = ()
    signing_checklist: tuple[str, ...] = ()
    post_contract_actions: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    generation_method: GenerationMethod
    provider_model: str | None = None
    fallback_reason: str | None = None

    @field_validator(
        "questions", "signing_checklist", "post_contract_actions", "source_ids"
    )
    @classmethod
    def _unique_non_empty(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_unique_non_empty(values, label="안내")

    @model_validator(mode="after")
    def _method_metadata(self) -> "RuleGuidance":
        if self.generation_method is GenerationMethod.PROVIDER:
            if self.provider_model is None or self.fallback_reason is not None:
                raise ValueError("provider 생성에는 provider_model만 필요합니다.")
        elif self.fallback_reason is None or self.provider_model is not None:
            raise ValueError("template fallback에는 fallback_reason만 필요합니다.")
        return self


class GenerationResult(BaseModel):
    """AnalysisRunResult와 별도로 유지하는 생성 결과 묶음."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_run_id: str = Field(min_length=1)
    items: tuple[RuleGuidance, ...]
    guardrail_passed: Literal[True] = True

    @model_validator(mode="after")
    def _unique_rules(self) -> "GenerationResult":
        rule_ids = [item.rule_id for item in self.items]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("생성 결과에는 중복 rule_id를 넣을 수 없습니다.")
        return self
