"""연습 답변 분류 provider의 고정 입출력 계약."""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lease_companion_ai.providers.errors import ProviderResponseValidationError
from lease_companion_ai.schemas.simulation import PracticeTurnEvaluation
from lease_companion_ai.schemas.unified import RuleStatus, Urgency


PRACTICE_PROMPT_VERSION: Final = "practice-evaluation-v1"


class PracticeRuleState(BaseModel):
    """Provider가 참고만 할 수 있는 규칙 상태 불변 스냅샷."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(pattern=r"^R\d{2}$")
    status: RuleStatus
    urgency: Urgency


class PracticeJudgmentState(BaseModel):
    """Provider가 참고만 할 수 있는 J 판정 불변 스냅샷."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    judgment_id: str = Field(pattern=r"^J(?:0[1-9]|1[0-2])$")
    status: RuleStatus
    urgency: Urgency


class PracticeEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_version: Literal["practice-evaluation-v1"] = PRACTICE_PROMPT_VERSION
    scenario_id: str = Field(pattern=r"^PRACTICE-[A-Z0-9-]+-\d{3}$")
    scenario_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    turn_id: str = Field(pattern=r"^TURN-\d{2}$")
    prompt: str = Field(min_length=1)
    user_answer: str = Field(min_length=1)
    response_time_seconds: float = Field(ge=0)
    goal_action_id: str = Field(pattern=r"^PA\d{2}$")
    required_semantics: tuple[str, ...] = Field(min_length=1)
    partial_semantics: tuple[str, ...] = Field(min_length=1)
    not_sufficient: tuple[str, ...] = Field(min_length=1)
    success_next_state: str = Field(min_length=1)
    retry_state: str = Field(pattern=r"^TURN-\d{2}$")
    rule_states: tuple[PracticeRuleState, ...] = Field(min_length=24, max_length=24)
    judgment_states: tuple[PracticeJudgmentState, ...] = ()


def load_practice_prompt(root: Path | None = None) -> str:
    prompt_root = root or Path(__file__).resolve().parents[3] / "prompts"
    prompt = (prompt_root / "simulation" / "v1.txt").read_text(encoding="utf-8")
    expected_header = f"버전: {PRACTICE_PROMPT_VERSION}"
    if not prompt.strip() or prompt.splitlines()[0].strip() != expected_header:
        raise ValueError(f"연습 평가 프롬프트 헤더는 {expected_header}이어야 합니다.")
    return prompt


@runtime_checkable
class PracticeAnswerProvider(Protocol):
    model_name: str

    def classify(
        self, request: PracticeEvaluationRequest
    ) -> PracticeTurnEvaluation: ...


def validate_provider_result(
    request: PracticeEvaluationRequest, result: PracticeTurnEvaluation
) -> PracticeTurnEvaluation:
    """응답 JSON Schema와 시나리오 상태 전이를 함께 검증한다."""

    try:
        validated = PracticeTurnEvaluation.model_validate(
            result.model_dump(mode="python")
        )
        if validated.turn_id != request.turn_id:
            raise ValueError("turn_id 불일치")
        if validated.answer_category == "appropriate_check":
            if validated.confirmed_action_ids != [request.goal_action_id]:
                raise ValueError("goal_action_id 불일치")
            if validated.next_dialogue_state != request.success_next_state:
                raise ValueError("success next state 불일치")
        elif validated.next_dialogue_state != request.retry_state:
            raise ValueError("retry state 불일치")
        return validated
    except (AttributeError, TypeError, ValueError, ValidationError):
        raise ProviderResponseValidationError(
            "practice provider 응답 검증에 실패했습니다."
        ) from None
