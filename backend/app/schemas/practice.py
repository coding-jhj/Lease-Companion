"""계약 연습 API wrapper.

시나리오·세션·평가의 도메인 본문은 AI canonical 타입을 재사용하고,
숨은 신호·정답표·미래 턴은 API 응답 모델에 넣지 않는다.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from lease_companion_ai.schemas.simulation import (
    PracticeResult,
    PracticeTurnEvaluation,
    ScenarioId,
    SelectedAction,
    SyntheticContractInput,
    WaitStep,
)

RequestId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{8,64}$")]


class PracticeScenarioSummary(BaseModel):
    scenario_id: ScenarioId
    scenario_version: str
    title: str
    role: str
    difficulty: str
    contract_stage: str
    always_show_labels: list[str]


class PracticeDialogueTurnView(BaseModel):
    turn_id: str
    prompt: str
    wait_sequence: list[WaitStep]


class PracticeScenarioDetail(PracticeScenarioSummary):
    synthetic_contract: SyntheticContractInput
    initial_turn: PracticeDialogueTurnView


class PracticeSessionCreateRequest(BaseModel):
    scenario_id: ScenarioId


class PracticeSessionResponse(BaseModel):
    practice_session_id: str
    scenario_id: ScenarioId
    scenario_version: str
    status: str
    current_state: str
    current_turn: PracticeDialogueTurnView | None
    confirmed_action_ids: list[str]
    selected_action: SelectedAction | None
    allowed_final_actions: list[SelectedAction]
    started_at: datetime
    completed_at: datetime | None = None


class PracticeTurnRequest(BaseModel):
    request_id: RequestId
    turn_id: str = Field(pattern=r"^TURN-\d{2}$")
    user_answer: str | None = Field(default=None, max_length=2_000)
    timed_out: bool = False
    response_time_seconds: float = Field(ge=0, le=3_600)

    @model_validator(mode="after")
    def _check_answer(self) -> "PracticeTurnRequest":
        if self.timed_out and self.user_answer is not None:
            raise ValueError("timed_out 요청에는 user_answer를 함께 넣을 수 없습니다.")
        if not self.timed_out and not (self.user_answer or "").strip():
            raise ValueError("대화 턴에는 user_answer가 필요합니다.")
        return self


class PracticeFinalActionRequest(BaseModel):
    request_id: RequestId
    selected_action: SelectedAction
    response_time_seconds: float = Field(default=0, ge=0, le=3_600)


class PracticeAdvanceRequest(BaseModel):
    request_id: RequestId
    turn_id: str = Field(pattern=r"^TURN-\d{2}$")
    destination: Literal["next_turn", "action_selection"]


class PracticeMediaJobResponse(BaseModel):
    media_job_id: str
    practice_turn_id: str
    status: Literal["queued", "generating_audio", "generating_video", "completed", "failed"]
    provider: str
    video_url: str | None = None
    error_code: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class PracticeTurnResponse(BaseModel):
    practice_turn_id: str
    attempt_no: int
    evaluation: PracticeTurnEvaluation | None
    dialogue_response: str | None
    media: PracticeMediaJobResponse | None = None
    session: PracticeSessionResponse


class PracticeConversationTurn(BaseModel):
    practice_turn_id: str
    turn_id: str
    prompt: str
    user_answer: str | None
    timed_out: bool
    dialogue_response: str | None
    created_at: datetime


class PracticeConversationPage(BaseModel):
    items: list[PracticeConversationTurn]
    next_cursor: str | None
    has_more: bool


class PracticeResultResponse(BaseModel):
    result: PracticeResult
