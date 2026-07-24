"""Grounded roleplay 대사 생성 provider의 고정 입출력 계약."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from lease_companion_ai.schemas.simulation import (
    AnswerCategory,
    ApprovedDialogueFact,
    SpeechAct,
)
from lease_companion_ai.simulation.dialogue_planner import DialoguePlan


class DialogueClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_id: str = Field(pattern=r"^F\d{2}$")
    relation: Literal["paraphrase"]


class DialogueGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_version: Literal["practice-dialogue-v1"]
    scenario_id: str = Field(pattern=r"^PRACTICE-[A-Z0-9-]+-\d{3}$")
    scenario_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    turn_id: str = Field(pattern=r"^TURN-\d{2}$")
    user_answer: str = Field(min_length=1)
    evaluation_category: AnswerCategory
    role: Literal["공인중개사"]
    approved_facts: tuple[ApprovedDialogueFact, ...] = ()
    plan: DialoguePlan
    allowed_entities: tuple[str, ...] = ()
    correction_codes: tuple[str, ...] = ()


class DialogueGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    response_text: str = Field(min_length=1)
    used_fact_ids: tuple[str, ...] = ()
    claims: tuple[DialogueClaim, ...] = ()
    speech_act: SpeechAct


class DialogueGenerationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_version: Literal["practice-dialogue-v1"]
    question_intent: str
    speech_act: SpeechAct
    allowed_fact_ids: tuple[str, ...] = ()
    used_fact_ids: tuple[str, ...] = ()
    validation_failure_codes: tuple[str, ...] = ()
    generation_attempts: int = Field(ge=0, le=2)
    fallback_used: bool
    provider_model: str | None = None


@runtime_checkable
class PracticeDialogueProvider(Protocol):
    model_name: str

    def generate(
        self, request: DialogueGenerationRequest
    ) -> DialogueGenerationResult: ...
