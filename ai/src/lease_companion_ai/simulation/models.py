"""승인된 연습 시나리오 정답표의 내부 검증 모델."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lease_companion_ai.schemas.simulation import AnswerCategory, ScenarioDefinition


class AnswerStatusDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status_id: AnswerCategory
    display_name: str = Field(min_length=1)
    meaning: str = Field(min_length=1)


class ActionRubric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str = Field(pattern=r"^PA\d{2}$")
    turn_id: str = Field(pattern=r"^TURN-\d{2}$")
    required_semantics: tuple[str, ...] = Field(min_length=1)
    partial_semantics: tuple[str, ...] = Field(min_length=1)
    not_sufficient: tuple[str, ...] = Field(min_length=1)


class EvaluationInputContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    elapsed_seconds: float | None = Field(default=None, ge=0)
    provider_error: Literal["timeout"] | None = None


class EvaluationExample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    example_id: str = Field(pattern=r"^EX-\d{3}$")
    turn_id: str = Field(pattern=r"^TURN-\d{2}$")
    user_input: str | None
    input_context: EvaluationInputContext
    expected_status_id: AnswerCategory
    expected_confirmed_action_ids: tuple[str, ...] = ()
    expected_next_turn_id: str = Field(min_length=1)


class DialogueResponseVariant(BaseModel):
    """같은 평가 범주 안에서도 질문 의도에 맞는 상대방 반응을 고른다."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    variant_id: str = Field(pattern=r"^DRV-[A-Z0-9-]+$")
    turn_id: str = Field(pattern=r"^TURN-\d{2}$")
    keyword_groups: tuple[tuple[str, ...], ...] = Field(min_length=1)
    response: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_keywords(self) -> "DialogueResponseVariant":
        if any(not group or any(not keyword.strip() for keyword in group) for group in self.keyword_groups):
            raise ValueError("dialogue response keyword_groups에는 빈 그룹·키워드를 넣을 수 없습니다.")
        return self


class DebriefDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_order: tuple[
        Literal[
            "confirmed_actions",
            "missed_actions",
            "recommended_phrases",
            "next_actions",
            "official_evidence",
        ],
        ...,
    ]
    recommended_phrases: tuple[str, ...] = Field(min_length=1)
    next_actions: tuple[str, ...] = Field(min_length=1)
    official_source_ids: tuple[str, ...] = Field(min_length=1)
    forbidden_conclusions: tuple[str, ...] = Field(min_length=1)


class PracticeAnswerKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_type: Literal["synthetic_practice_answer_key"]
    scenario_id: str = Field(pattern=r"^PRACTICE-[A-Z0-9-]+-\d{3}$")
    scenario_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    answer_key_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    review_status: Literal["approved"]
    answer_statuses: tuple[AnswerStatusDefinition, ...] = Field(min_length=6)
    action_rubrics: tuple[ActionRubric, ...] = Field(min_length=1)
    evaluation_examples: tuple[EvaluationExample, ...] = Field(min_length=1)
    dialogue_response_variants: tuple[DialogueResponseVariant, ...] = ()
    debrief: DebriefDefinition

    @model_validator(mode="after")
    def _check_references(self) -> "PracticeAnswerKey":
        statuses = [item.status_id for item in self.answer_statuses]
        expected_statuses = [
            "appropriate_check",
            "partial_check",
            "ambiguous_answer",
            "avoidance",
            "no_response",
            "needs_review",
        ]
        if statuses != expected_statuses:
            raise ValueError("answer_statuses는 승인된 6개 상태를 순서대로 포함해야 합니다.")
        rubric_actions = [item.action_id for item in self.action_rubrics]
        rubric_turns = [item.turn_id for item in self.action_rubrics]
        if len(rubric_actions) != len(set(rubric_actions)):
            raise ValueError("action_rubrics에 중복 action_id가 있습니다.")
        if len(rubric_turns) != len(set(rubric_turns)):
            raise ValueError("action_rubrics에 중복 turn_id가 있습니다.")
        example_ids = [item.example_id for item in self.evaluation_examples]
        if len(example_ids) != len(set(example_ids)):
            raise ValueError("evaluation_examples에 중복 example_id가 있습니다.")
        variant_ids = [item.variant_id for item in self.dialogue_response_variants]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("dialogue_response_variants에 중복 variant_id가 있습니다.")
        if any(item.turn_id not in set(rubric_turns) for item in self.dialogue_response_variants):
            raise ValueError("dialogue_response_variants가 정의되지 않은 turn을 참조합니다.")
        return self


def load_practice_assets(
    scenario_path: Path, answer_key_path: Path
) -> tuple[ScenarioDefinition, PracticeAnswerKey]:
    """승인된 합성 시나리오와 정답표를 함께 검증한다."""

    scenario = ScenarioDefinition.model_validate_json(
        scenario_path.read_text(encoding="utf-8")
    )
    answer_key = PracticeAnswerKey.model_validate_json(
        answer_key_path.read_text(encoding="utf-8")
    )
    if scenario.review_status != "approved":
        raise ValueError("승인된 시나리오만 평가에 사용할 수 있습니다.")
    if (
        answer_key.scenario_id != scenario.scenario_id
        or answer_key.scenario_version != scenario.scenario_version
    ):
        raise ValueError("시나리오와 정답표의 ID·버전이 일치하지 않습니다.")
    expected_pairs = {
        (turn.turn_id, turn.goal_action_id) for turn in scenario.dialogue_turns
    }
    actual_pairs = {
        (rubric.turn_id, rubric.action_id) for rubric in answer_key.action_rubrics
    }
    if actual_pairs != expected_pairs:
        raise ValueError("시나리오 turn/action과 정답표 rubric이 일치하지 않습니다.")
    return scenario, answer_key
