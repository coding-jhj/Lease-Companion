"""계약 연습 시뮬레이션 canonical runtime schema.

실제 계약 분석 데이터와 연습 데이터를 분리한다. 연습 스키마에는 contract_id,
input_snapshot_id, analysis_run_id를 사용하지 않는다.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .unified import SCHEMA_VERSION, ClauseCandidate, ContractType, SchemaVersion


ScenarioId = Annotated[str, Field(pattern=r"^PRACTICE-[A-Z0-9-]+-\d{3}$")]
ScenarioVersion = str
ActionId = str
TurnId = str
AnswerCategory = Literal[
    "appropriate_check",
    "partial_check",
    "ambiguous_answer",
    "avoidance",
    "no_response",
    "needs_review",
]
SelectedAction = Literal["진행", "추가 확인", "특약 수정 요구", "보류", "중단"]


T = TypeVar("T")


def _unique(values: list[T], *, label: str) -> list[T]:
    if len(values) != len(set(values)):
        raise ValueError(f"중복 {label}가 있습니다.")
    return values


class SyntheticContractInput(BaseModel):
    """승인 fixture의 합성 계약 사실. 실제 계약 건과 연결하지 않는다."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_type: ContractType
    signed: bool
    deposit_paid: bool
    property_address: str = Field(min_length=1)
    deposit: int = Field(ge=0)
    monthly_rent: int | None = Field(default=None, ge=0)
    contract_payment: int = Field(ge=0)
    balance_payment: int = Field(ge=0)
    requested_provisional_payment: int = Field(ge=0)
    contract_payment_date: date
    balance_payment_date: date
    move_in_date: date
    start_date: date
    end_date: date
    landlord_name: str = Field(min_length=1)
    broker_name: str = Field(min_length=1)
    is_proxy_contract: bool = False
    agent_name: str | None = None
    agent_relationship: str | None = None
    proxy_authority_documents: list[str] = Field(default_factory=list)
    account_holder: str = Field(min_length=1)
    account_number_stored: bool
    registry_issue_date: date
    registry_property_address: str = Field(min_length=1)
    owner_names: list[str] = Field(min_length=1)
    is_joint_ownership: bool
    owner_shares: dict[str, str]
    mortgage_present: bool
    mortgage_maximum_claim: int | None = Field(default=None, ge=0)
    deposit_return_clause: str = Field(min_length=1)
    rights_change_clause_present: bool
    special_clauses: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_owner_data(self) -> "SyntheticContractInput":
        _unique(self.owner_names, label="owner_names")
        if set(self.owner_shares) != set(self.owner_names):
            raise ValueError("owner_shares는 owner_names와 정확히 일치해야 합니다.")
        if self.is_joint_ownership is not (len(self.owner_names) > 1):
            raise ValueError("is_joint_ownership와 owner_names 수가 일치하지 않습니다.")
        if not self.is_proxy_contract and any(
            value is not None for value in (self.agent_name, self.agent_relationship)
        ):
            raise ValueError("대리 계약이 아니면 대리인 정보를 넣을 수 없습니다.")
        if not self.is_proxy_contract and self.proxy_authority_documents:
            raise ValueError("대리 계약이 아니면 권한 서류를 넣을 수 없습니다.")
        return self


class TargetAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: ActionId = Field(pattern=r"^PA\d{2}$")
    name: str = Field(min_length=1)
    linked_signal_ids: list[str] = Field(default_factory=list)

    @field_validator("linked_signal_ids")
    @classmethod
    def _check_signal_ids(cls, values: list[str]) -> list[str]:
        return _unique(values, label="linked_signal_ids")


class ConfirmationSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    signal_id: str = Field(pattern=r"^SIG-[A-Z0-9-]+$")
    fact: str = Field(min_length=1)
    linked_rule_ids: list[str] = Field(default_factory=list)
    linked_judgment_ids: list[str] = Field(default_factory=list)
    official_source_ids: list[str] = Field(min_length=1)

    @field_validator("linked_rule_ids")
    @classmethod
    def _check_rule_ids(cls, values: list[str]) -> list[str]:
        if any(not re.fullmatch(r"R\d{2}", value) for value in values):
            raise ValueError("linked_rule_ids는 R 번호여야 합니다.")
        return _unique(values, label="linked_rule_ids")

    @field_validator("linked_judgment_ids")
    @classmethod
    def _check_judgment_ids(cls, values: list[str]) -> list[str]:
        allowed = {f"J{index:02d}" for index in range(1, 13)}
        if any(value not in allowed for value in values):
            raise ValueError("linked_judgment_ids는 J01~J12여야 합니다.")
        return _unique(values, label="linked_judgment_ids")

    @field_validator("official_source_ids")
    @classmethod
    def _check_source_ids(cls, values: list[str]) -> list[str]:
        if any(not value.startswith("SRC-") for value in values):
            raise ValueError("official_source_ids는 SRC- 식별자여야 합니다.")
        return _unique(values, label="official_source_ids")


class WaitStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal["WAIT_BASIC", "WAIT_PRESSURE", "PRESSURE_REMINDER"]
    from_second: int = Field(ge=0)
    to_second: int | None = Field(default=None, gt=0)
    line: str | None = None

    @model_validator(mode="after")
    def _check_range(self) -> "WaitStep":
        if self.to_second is not None and self.to_second <= self.from_second:
            raise ValueError("to_second는 from_second보다 커야 합니다.")
        return self


class DialogueResponses(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    appropriate_check: str = Field(min_length=1)
    partial_check: str = Field(min_length=1)
    ambiguous_answer: str = Field(min_length=1)
    avoidance: str = Field(min_length=1)
    no_response: str = Field(min_length=1)
    needs_review: str = Field(min_length=1)


class DialogueTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_id: TurnId = Field(pattern=r"^TURN-\d{2}$")
    goal_action_id: ActionId = Field(pattern=r"^PA\d{2}$")
    prompt: str = Field(min_length=1)
    wait_sequence: list[WaitStep] = Field(default_factory=list)
    responses: DialogueResponses
    next_turn_id: str = Field(min_length=1)


class ActionSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state_id: str = Field(min_length=1)
    allowed_actions: list[SelectedAction] = Field(min_length=1)
    next_state_id: str = Field(min_length=1)

    @field_validator("allowed_actions")
    @classmethod
    def _check_actions(cls, values: list[SelectedAction]) -> list[SelectedAction]:
        return _unique(values, label="allowed_actions")


class ScenarioDefinition(BaseModel):
    """버전 고정된 승인 합성 시나리오."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    fixture_type: Literal["synthetic_practice_scenario"]
    data_classification: Literal["synthetic"]
    scenario_id: ScenarioId
    scenario_version: ScenarioVersion = Field(pattern=r"^\d+\.\d+\.\d+$")
    review_status: Literal["draft", "approved"]
    title: str = Field(min_length=1)
    role: Literal["공인중개사", "임대인"]
    difficulty: Literal["기본", "중급", "고급"]
    contract_stage: str = Field(min_length=1)
    always_show_labels: list[str] = Field(min_length=2)
    synthetic_contract: SyntheticContractInput
    classification_candidates: list[ClauseCandidate] = Field(default_factory=list)
    target_actions: list[TargetAction] = Field(min_length=1)
    hidden_confirmation_signals: list[ConfirmationSignal] = Field(min_length=1)
    dialogue_turns: list[DialogueTurn] = Field(min_length=1)
    action_selection: ActionSelection
    terminal_state_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_references(self) -> "ScenarioDefinition":
        action_ids = [item.action_id for item in self.target_actions]
        signal_ids = [item.signal_id for item in self.hidden_confirmation_signals]
        turn_ids = [item.turn_id for item in self.dialogue_turns]
        _unique(action_ids, label="action_id")
        _unique(signal_ids, label="signal_id")
        _unique(turn_ids, label="turn_id")
        _unique(self.always_show_labels, label="always_show_labels")
        _unique(
            [candidate.clause_ref for candidate in self.classification_candidates],
            label="classification_candidates clause_ref",
        )

        known_actions = set(action_ids)
        known_signals = set(signal_ids)
        for action in self.target_actions:
            if not set(action.linked_signal_ids) <= known_signals:
                raise ValueError(f"{action.action_id}의 linked_signal_ids에 없는 신호가 있습니다.")
        for turn in self.dialogue_turns:
            if turn.goal_action_id not in known_actions:
                raise ValueError(f"{turn.turn_id}의 goal_action_id가 target_actions에 없습니다.")
            if turn.next_turn_id not in {*turn_ids, self.action_selection.state_id}:
                raise ValueError(f"{turn.turn_id}의 next_turn_id가 정의되지 않았습니다.")
        if self.terminal_state_id != self.action_selection.next_state_id:
            raise ValueError("terminal_state_id는 action_selection.next_state_id와 같아야 합니다.")
        return self


class ScenarioMediaClip(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal[
        "intro",
        "waiting_soft",
        "waiting_pressure",
        "reprompt",
        "reaction_positive",
        "reaction_retry",
        "next_turn",
        "result",
    ]
    poster_url: str = Field(min_length=1)
    subtitle: str = Field(min_length=1)
    loop: bool
    desktop_video_url: str | None = None
    mobile_video_url: str | None = None

    @model_validator(mode="after")
    def _check_viewports(self) -> "ScenarioMediaClip":
        if not self.desktop_video_url or not self.mobile_video_url:
            raise ValueError("desktop 및 mobile 영상 자산이 모두 필요합니다.")
        return self


class ScenarioMediaManifest(BaseModel):
    """시나리오 버전에 고정된 상태별 사전 생성 미디어."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    scenario_id: ScenarioId
    scenario_version: ScenarioVersion = Field(pattern=r"^\d+\.\d+\.\d+$")
    media_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    clips: list[ScenarioMediaClip] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_states(self) -> "ScenarioMediaManifest":
        states = [clip.state for clip in self.clips]
        if len(states) != len(set(states)):
            raise ValueError("중복 media state가 있습니다.")
        return self


class PracticeSessionState(BaseModel):
    """연습 세션의 복원 가능한 현재 상태."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    session_id: str = Field(min_length=1)
    user_id: int = Field(gt=0, strict=True)
    scenario_id: ScenarioId
    scenario_version: ScenarioVersion = Field(pattern=r"^\d+\.\d+\.\d+$")
    current_state: str = Field(min_length=1)
    started_at: datetime
    status: Literal["active", "completed", "abandoned"]
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def _check_completion(self) -> "PracticeSessionState":
        if self.status == "completed" and self.completed_at is None:
            raise ValueError("completed 상태에는 completed_at이 필요합니다.")
        if self.status == "active" and self.completed_at is not None:
            raise ValueError("active 상태에는 completed_at을 넣을 수 없습니다.")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at은 started_at보다 빠를 수 없습니다.")
        return self


class PracticeTurnInput(BaseModel):
    """사용자 답변 또는 행동 선택 1회."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    session_id: str = Field(min_length=1)
    turn_id: str = Field(pattern=r"^(?:TURN-\d{2}|ACTION-SELECTION)$")
    user_answer: str | None = None
    selected_action: SelectedAction | None = None
    timed_out: bool = False
    response_time_seconds: float = Field(ge=0)

    @field_validator("user_answer")
    @classmethod
    def _strip_answer(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _check_input(self) -> "PracticeTurnInput":
        has_input = self.user_answer is not None or self.selected_action is not None
        if self.timed_out and has_input:
            raise ValueError("timed_out 입력에는 답변 또는 행동을 함께 넣을 수 없습니다.")
        if not self.timed_out and not has_input:
            raise ValueError("사용자 답변 또는 행동 중 하나가 필요합니다.")
        if self.turn_id == "ACTION-SELECTION" and self.selected_action is None:
            raise ValueError("ACTION-SELECTION에는 selected_action이 필요합니다.")
        return self


class PracticeTurnEvaluation(BaseModel):
    """연습 행동 평가 결과. 계약 규칙 상태와 분리한다."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    turn_id: TurnId = Field(pattern=r"^TURN-\d{2}$")
    answer_category: AnswerCategory
    confirmed_action_ids: list[ActionId] = Field(default_factory=list)
    next_dialogue_state: str = Field(min_length=1)
    fallback_reason: str | None = None
    evidence_text: str | None = None

    @field_validator("evidence_text")
    @classmethod
    def _strip_evidence(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _check_evaluation(self) -> "PracticeTurnEvaluation":
        _unique(self.confirmed_action_ids, label="confirmed_action_ids")
        if any(re.fullmatch(r"PA\d{2}", value) is None for value in self.confirmed_action_ids):
            raise ValueError("confirmed_action_ids는 PA 번호여야 합니다.")
        if self.answer_category == "appropriate_check" and not self.confirmed_action_ids:
            raise ValueError("appropriate_check에는 확인된 행동이 필요합니다.")
        if self.answer_category != "appropriate_check" and self.confirmed_action_ids:
            raise ValueError("appropriate_check 외 범주에는 확인된 행동을 넣을 수 없습니다.")
        if self.answer_category == "needs_review":
            if not self.fallback_reason:
                raise ValueError("needs_review에는 fallback_reason이 필요합니다.")
        elif self.fallback_reason is not None:
            raise ValueError("needs_review가 아니면 fallback_reason을 넣을 수 없습니다.")
        return self


class PracticeResult(BaseModel):
    """점수 없이 행동·신호·공식 근거로 구성한 최종 복기."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    session_id: str = Field(min_length=1)
    scenario_id: ScenarioId
    scenario_version: ScenarioVersion = Field(pattern=r"^\d+\.\d+\.\d+$")
    confirmed_action_ids: list[ActionId] = Field(default_factory=list)
    missed_action_ids: list[ActionId] = Field(default_factory=list)
    confirmed_actions: list[str] = Field(default_factory=list)
    missed_signals: list[str] = Field(default_factory=list)
    recommended_phrases: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    official_source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_result(self) -> "PracticeResult":
        for name in (
            "confirmed_action_ids",
            "missed_action_ids",
            "confirmed_actions",
            "missed_signals",
            "recommended_phrases",
            "next_actions",
            "official_source_ids",
        ):
            _unique(getattr(self, name), label=name)
        if set(self.confirmed_action_ids) & set(self.missed_action_ids):
            raise ValueError("같은 행동을 확인·누락 목록에 동시에 넣을 수 없습니다.")
        return self
