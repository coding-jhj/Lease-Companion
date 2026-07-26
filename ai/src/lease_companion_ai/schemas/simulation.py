"""계약 연습 시뮬레이션 canonical runtime schema.

실제 계약 분석 데이터와 연습 데이터를 분리한다. 연습 스키마에는 contract_id,
input_snapshot_id, analysis_run_id를 사용하지 않는다.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .unified import (
    JUDGMENT_IDS,
    SCHEMA_VERSION,
    ClauseCandidate,
    ContractType,
    SchemaVersion,
)


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
PracticeEndingType = Literal[
    "rights_asserted",
    "insufficient_protection",
    "transaction_stopped",
]

# 계약 대화 연습은 정답을 맞힐 때까지 같은 장면을 반복하는 퀴즈가 아니다.
# 사용자가 한 번 응답한 결과는 확인 행동 인정 여부와 별개로 저장하고 다음 장면으로
# 진행한다. provider 장애·timeout·형식 오류인 needs_review만 사용자 오답으로
# 기록하지 않고 현재 장면에서 재시도 또는 명시적 건너뛰기를 선택하게 한다.
_RETRY_ONLY_CATEGORIES = frozenset({"needs_review"})

# 분기형 흐름(branching_flow)에서 애매·부분 답변에 상대방이 같은 장면에서 재질문할 수
# 있는 최대 횟수. 이 횟수를 넘기면 확인하지 못한 내용으로 남기고 다음 장면으로 넘어간다.
# 같은 질문을 두 번 넘게 되묻으면 연습이 정답 맞히기처럼 느껴지므로 1회로 제한한다.
# 정답 답변의 회유·압박은 시나리오의 다음 TURN 대사가 담당한다.
PRESSURE_REPEAT_LIMIT = 1
_PRESSURE_CATEGORIES = frozenset({"partial_check", "ambiguous_answer"})


def allowed_next_dialogue_states(
    answer_category: "AnswerCategory", success_next_state: str, retry_state: str
) -> frozenset[str]:
    """답변 분류별 허용 다음 대화 상태.

    needs_review → 재시도만, 그 외 사용자 응답 범주 → 진행만.
    확인 행동 인정 여부는 confirmed_action_ids에 누적하고 마지막 복기에서 안내한다.
    """
    if answer_category in _RETRY_ONLY_CATEGORIES:
        return frozenset({retry_state})
    return frozenset({success_next_state})


def resolve_next_dialogue_state(
    answer_category: "AnswerCategory",
    *,
    turn_id: str,
    next_turn_id: str,
    action_selection_state: str,
    pressure_rounds: int,
    branching_flow: bool,
) -> str:
    """상태 머신이 정하는 결정적 다음 대화 상태.

    선형 흐름: needs_review(provider 실패)만 현재 장면 유지, 그 외는 다음 장면.
    분기 흐름: 조건 수용(avoidance)은 즉시 최종 계약 결정, 부분·애매 답변은
    PRESSURE_REPEAT_LIMIT까지 같은 장면에서 재질문을 이어 간다.
    """
    if answer_category in _RETRY_ONLY_CATEGORIES:
        return turn_id
    if not branching_flow:
        return next_turn_id
    if answer_category == "avoidance":
        return action_selection_state
    if (
        answer_category in _PRESSURE_CATEGORIES
        and pressure_rounds < PRESSURE_REPEAT_LIMIT
    ):
        return turn_id
    return next_turn_id


SelectedAction = Literal["진행", "추가 확인", "특약 수정 요구", "보류", "중단"]
ActionEffect = Literal[
    "document_or_clause_request",
    "contract_or_signing_hold",
    "payment_hold",
]
VerbalRelianceObservation = Literal["not_observed", "relied", "rejected"]
VerbalReliance = Literal["not_observed", "relied", "rejected", "mixed"]


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
    effect_tags: list[ActionEffect] = Field(default_factory=list)

    @field_validator("linked_signal_ids", "effect_tags")
    @classmethod
    def _check_action_lists(
        cls, values: list[str], info: ValidationInfo
    ) -> list[str]:
        return _unique(values, label=info.field_name or "action_list")


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
        # 판정 축이 늘어날 때 이 목록이 뒤처지지 않도록 canonical 상수에서 파생한다.
        allowed = set(JUDGMENT_IDS)
        if any(value not in allowed for value in values):
            raise ValueError(f"linked_judgment_ids는 {JUDGMENT_IDS[0]}~{JUDGMENT_IDS[-1]}여야 합니다.")
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


DialogueIntent = Literal[
    "clause_meaning",
    "return_timing",
    "no_successor_case",
    "verbal_promise",
    "contract_fact",
    "clause_change_request",
    "contract_hold",
    "unrelated",
    "unknown",
]
SpeechAct = Literal[
    "answer_fact",
    "state_missing_fact",
    "relay_landlord_claim",
    "acknowledge_request",
    "maintain_position",
    "respond_to_hold",
    "clarify_user_intent",
    "decline_unrelated",
]
ClaimKind = Literal[
    "documented_fact",
    "missing_information",
    "reported_statement",
]
DisclosurePolicy = Literal["on_request", "restricted", "unknown"]


class ApprovedDialogueFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_id: str = Field(pattern=r"^F\d{2}$")
    canonical_text: str = Field(min_length=1)
    allowed_intents: list[DialogueIntent] = Field(min_length=1)
    claim_kind: ClaimKind
    disclosure: DisclosurePolicy

    @field_validator("allowed_intents")
    @classmethod
    def _check_allowed_intents(
        cls, values: list[DialogueIntent]
    ) -> list[DialogueIntent]:
        return _unique(values, label="allowed_intents")


class GroundedRoleplayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_version: Literal["practice-dialogue-v1"]
    approved_facts: list[ApprovedDialogueFact] = Field(min_length=1)
    intent_keywords: dict[DialogueIntent, list[str]]
    fallbacks: dict[SpeechAct, list[str]]

    @model_validator(mode="after")
    def _check_config(self) -> "GroundedRoleplayConfig":
        fact_ids = [fact.fact_id for fact in self.approved_facts]
        _unique(fact_ids, label="fact_id")
        if any(not keywords or any(not keyword.strip() for keyword in keywords)
               for keywords in self.intent_keywords.values()):
            raise ValueError("intent_keywords에는 빈 목록·키워드를 넣을 수 없습니다.")
        expected_speech_acts = {
            "answer_fact",
            "state_missing_fact",
            "relay_landlord_claim",
            "acknowledge_request",
            "maintain_position",
            "respond_to_hold",
            "clarify_user_intent",
            "decline_unrelated",
        }
        if set(self.fallbacks) != expected_speech_acts:
            raise ValueError("fallbacks는 모든 speech_act를 포함해야 합니다.")
        if any(
            len(lines) < 2 or any(not line.strip() for line in lines)
            for lines in self.fallbacks.values()
        ):
            raise ValueError("각 speech_act fallback은 검수 문장 두 개 이상이어야 합니다.")
        return self


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
    grounded_roleplay: GroundedRoleplayConfig | None = None
    # 조건 수용 즉시 계약 결정·회유 반복이 있는 분기형 흐름 여부. 미지정 시 선형 흐름.
    branching_flow: bool = False
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
    evaluations: list[PracticeTurnEvaluation] = Field(default_factory=list)
    confirmed_action_ids: list[ActionId] = Field(default_factory=list)
    recognized_signal_ids: list[str] = Field(default_factory=list)
    verbal_reliance: VerbalReliance = "not_observed"
    document_or_clause_requested: bool = False
    contract_or_signing_held: bool = False
    payment_held: bool = False
    evidence_texts: list[str] = Field(default_factory=list)
    no_response_counts: dict[TurnId, int] = Field(default_factory=dict)
    pressure_counts: dict[TurnId, int] = Field(default_factory=dict)
    # 직전 사용자 발화에서 확정한 대화 주제. 새 의도가 없는 짧은 동의·반복 답변에
    # 상대방이 같은 질문을 되묻지 않도록 이어 쓴다.
    last_dialogue_intent: DialogueIntent | None = None
    selected_action: SelectedAction | None = None

    @model_validator(mode="after")
    def _check_completion(self) -> "PracticeSessionState":
        if self.status == "completed" and self.completed_at is None:
            raise ValueError("completed 상태에는 completed_at이 필요합니다.")
        if self.status == "completed" and self.selected_action is None:
            raise ValueError("completed 상태에는 selected_action이 필요합니다.")
        if self.status == "active" and self.completed_at is not None:
            raise ValueError("active 상태에는 completed_at을 넣을 수 없습니다.")
        if self.status == "active" and self.selected_action is not None:
            raise ValueError("active 상태에는 selected_action을 넣을 수 없습니다.")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at은 started_at보다 빠를 수 없습니다.")
        _unique(self.confirmed_action_ids, label="confirmed_action_ids")
        _unique(self.recognized_signal_ids, label="recognized_signal_ids")
        _unique(self.evidence_texts, label="evidence_texts")
        if any(re.fullmatch(r"PA\d{2}", value) is None for value in self.confirmed_action_ids):
            raise ValueError("confirmed_action_ids는 PA 번호여야 합니다.")
        if any(
            re.fullmatch(r"SIG-[A-Z0-9-]+", value) is None
            for value in self.recognized_signal_ids
        ):
            raise ValueError("recognized_signal_ids는 SIG 식별자여야 합니다.")
        if any(
            re.fullmatch(r"TURN-\d{2}", turn_id) is None or count < 1
            for turn_id, count in self.no_response_counts.items()
        ):
            raise ValueError("no_response_counts는 TURN별 1 이상의 횟수여야 합니다.")
        if any(
            re.fullmatch(r"TURN-\d{2}", turn_id) is None
            or not 1 <= count <= PRESSURE_REPEAT_LIMIT
            for turn_id, count in self.pressure_counts.items()
        ):
            raise ValueError(
                f"pressure_counts는 TURN별 1~{PRESSURE_REPEAT_LIMIT}회여야 합니다."
            )
        evaluation_actions = list(
            dict.fromkeys(
                action_id
                for evaluation in self.evaluations
                for action_id in evaluation.confirmed_action_ids
            )
        )
        if evaluation_actions != self.confirmed_action_ids:
            raise ValueError("evaluations와 confirmed_action_ids가 일치해야 합니다.")
        evaluation_evidence = list(
            dict.fromkeys(
                evaluation.evidence_text
                for evaluation in self.evaluations
                if evaluation.evidence_text is not None
            )
        )
        if evaluation_evidence != self.evidence_texts:
            raise ValueError("evaluations와 evidence_texts가 일치해야 합니다.")
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
    verbal_reliance: VerbalRelianceObservation = "not_observed"
    # 답변 의미를 한 곳에서만 해석하기 위해, 대화 의도와 행동 의도를 평가 결과에 함께
    # 싣는다. 상대방 대사 생성은 이 값을 다시 추론하지 않고 그대로 사용한다.
    # 두 값 모두 Python이 정하며 provider 응답으로 덮어쓰지 않는다.
    dialogue_intent: DialogueIntent | None = None
    action_intent: SelectedAction | None = None

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
    ending_type: PracticeEndingType = "insufficient_protection"
    ending_title: str = "확인 행동을 더 구체적으로 표현해 보세요"
    feedback_label: str = "보완할 점"
    feedback: str = "중요한 조건을 확인하고 문서로 남기겠다는 의사를 더 명확하게 표현할 필요가 있습니다."
    practice_phrase: str = "확인 자료와 수정된 계약 문구를 보기 전에는 계약이나 송금을 진행하지 않겠습니다."
    action_summary: list[str] = Field(
        default_factory=lambda: [
            "중요한 조건을 계약서와 공식 자료로 확인한다.",
            "구두 설명은 계약서나 특약 문구로 남긴다.",
            "확인이 끝나기 전에는 계약·서명·송금을 보류한다.",
        ],
        min_length=3,
        max_length=3,
    )
    selected_action: SelectedAction | None = None
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
            "action_summary",
        ):
            _unique(getattr(self, name), label=name)
        if set(self.confirmed_action_ids) & set(self.missed_action_ids):
            raise ValueError("같은 행동을 확인·누락 목록에 동시에 넣을 수 없습니다.")
        return self
