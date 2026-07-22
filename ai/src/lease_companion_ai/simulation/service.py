"""연습 턴 평가와 안전 fallback을 조정한다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime

from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderResponseValidationError,
)
from lease_companion_ai.schemas.simulation import (
    PracticeResult,
    PracticeSessionState,
    PracticeTurnEvaluation,
    PracticeTurnInput,
    ScenarioDefinition,
)
from lease_companion_ai.schemas.unified import (
    OfficialSource,
    RuleResult,
    RuleStatus,
    Urgency,
)
from lease_companion_ai.simulation.debrief import build_practice_result
from lease_companion_ai.simulation.models import PracticeAnswerKey
from lease_companion_ai.simulation.provider import (
    PRACTICE_PROMPT_VERSION,
    PracticeAnswerProvider,
    PracticeEvaluationRequest,
    PracticeJudgmentState,
    PracticeRuleState,
    validate_provider_result,
)
from lease_companion_ai.simulation.rules import (
    run_practice_judgments,
    run_practice_rules,
)
from lease_companion_ai.simulation.state_machine import (
    advance_dialogue,
    complete_action_selection,
    start_practice_session,
    validate_session,
)


@dataclass(frozen=True)
class PracticeStep:
    session: PracticeSessionState
    evaluation: PracticeTurnEvaluation | None = None
    dialogue_response: str | None = None
    result: PracticeResult | None = None


class PracticeEvaluationService:
    def __init__(
        self,
        scenario: ScenarioDefinition,
        answer_key: PracticeAnswerKey,
        provider: PracticeAnswerProvider | None = None,
    ) -> None:
        if (
            scenario.scenario_id != answer_key.scenario_id
            or scenario.scenario_version != answer_key.scenario_version
        ):
            raise ValueError("시나리오와 정답표가 일치하지 않습니다.")
        self._scenario = scenario
        self._answer_key = answer_key
        self._provider = provider
        self._rule_results = run_practice_rules(scenario)
        self._judgment_results = run_practice_judgments(scenario)

    @property
    def rule_results(self) -> tuple[RuleResult, ...]:
        return deepcopy(self._rule_results)

    def evaluate(self, turn_input: PracticeTurnInput) -> PracticeTurnEvaluation:
        if turn_input.turn_id == "ACTION-SELECTION":
            raise ValueError("행동 선택은 대화 답변 평가 대상이 아닙니다.")
        turn = next(
            (item for item in self._scenario.dialogue_turns if item.turn_id == turn_input.turn_id),
            None,
        )
        if turn is None:
            raise ValueError("시나리오에 없는 turn_id입니다.")
        if turn_input.timed_out:
            return PracticeTurnEvaluation(
                turn_id=turn.turn_id,
                answer_category="no_response",
                confirmed_action_ids=[],
                next_dialogue_state=turn.turn_id,
            )
        if turn_input.user_answer is None:
            raise ValueError("대화 턴에는 사용자 답변이 필요합니다.")
        if self._provider is None:
            return self._fallback(
                turn.turn_id, "provider_unavailable", turn_input.user_answer
            )

        rubric = next(
            item for item in self._answer_key.action_rubrics if item.turn_id == turn.turn_id
        )
        rule_states = tuple(
            PracticeRuleState(
                rule_id=result.rule_id,
                status=RuleStatus(result.status),
                urgency=Urgency(result.urgency),
            )
            for result in self._rule_results
        )
        request = PracticeEvaluationRequest(
            prompt_version=PRACTICE_PROMPT_VERSION,
            scenario_id=self._scenario.scenario_id,
            scenario_version=self._scenario.scenario_version,
            turn_id=turn.turn_id,
            prompt=turn.prompt,
            user_answer=turn_input.user_answer,
            response_time_seconds=turn_input.response_time_seconds,
            goal_action_id=turn.goal_action_id,
            required_semantics=rubric.required_semantics,
            partial_semantics=rubric.partial_semantics,
            not_sufficient=rubric.not_sufficient,
            success_next_state=turn.next_turn_id,
            retry_state=turn.turn_id,
            rule_states=rule_states,
            judgment_states=tuple(
                PracticeJudgmentState(
                    judgment_id=result.judgment_id,
                    status=result.status,
                    urgency=result.urgency,
                )
                for result in self._judgment_results
            ),
        )
        before = self._state_fingerprint(
            request.rule_states, request.judgment_states
        )
        try:
            result = self._provider.classify(request)
        except TimeoutError:
            return self._fallback(
                turn.turn_id, "provider_timeout", turn_input.user_answer
            )
        except ProviderResponseValidationError:
            return self._fallback(
                turn.turn_id,
                "response_validation_failed",
                turn_input.user_answer,
            )
        except ProviderError:
            return self._fallback(
                turn.turn_id, "provider_error", turn_input.user_answer
            )
        except Exception:
            return self._fallback(
                turn.turn_id, "provider_error", turn_input.user_answer
            )
        if (
            self._state_fingerprint(request.rule_states, request.judgment_states)
            != before
        ):
            return self._fallback(
                turn.turn_id, "rule_mutation", turn_input.user_answer
            )
        try:
            validated = validate_provider_result(request, result)
            return validated.model_copy(
                update={"evidence_text": turn_input.user_answer}
            )
        except ProviderResponseValidationError:
            return self._fallback(
                turn.turn_id,
                "response_validation_failed",
                turn_input.user_answer,
            )

    @staticmethod
    def _state_fingerprint(
        rule_states: tuple[PracticeRuleState, ...],
        judgment_states: tuple[PracticeJudgmentState, ...],
    ) -> tuple[tuple[str, RuleStatus, Urgency], ...]:
        return tuple(
            (item.rule_id, item.status, item.urgency) for item in rule_states
        ) + tuple(
            (item.judgment_id, item.status, item.urgency)
            for item in judgment_states
        )

    @staticmethod
    def _fallback(
        turn_id: str, reason: str, evidence_text: str | None
    ) -> PracticeTurnEvaluation:
        return PracticeTurnEvaluation(
            turn_id=turn_id,
            answer_category="needs_review",
            confirmed_action_ids=[],
            next_dialogue_state=turn_id,
            fallback_reason=reason,
            evidence_text=evidence_text,
        )


class PracticeSimulationService:
    """한 턴 평가를 세션 상태 전이와 최종 복기에 연결한다."""

    def __init__(
        self,
        scenario: ScenarioDefinition,
        answer_key: PracticeAnswerKey,
        provider: PracticeAnswerProvider | None = None,
    ) -> None:
        self._scenario = scenario
        self._answer_key = answer_key
        self.evaluation = PracticeEvaluationService(
            scenario, answer_key, provider
        )

    def start_session(
        self,
        session_id: str,
        user_id: int,
        started_at: datetime,
    ) -> PracticeSessionState:
        return start_practice_session(
            self._scenario, session_id, user_id, started_at
        )

    def submit(
        self,
        session: PracticeSessionState,
        turn_input: PracticeTurnInput,
        *,
        occurred_at: datetime,
        evidence_by_action: Mapping[str, Sequence[OfficialSource]] | None = None,
    ) -> PracticeStep:
        validate_session(session, self._scenario, turn_input)
        if turn_input.turn_id == self._scenario.action_selection.state_id:
            completed = complete_action_selection(
                session, self._scenario, turn_input, occurred_at
            )
            result = build_practice_result(
                session.session_id,
                self._scenario,
                self._answer_key,
                completed.evaluations,
                evidence_by_action or {},
                selected_action=completed.selected_action,
            )
            return PracticeStep(session=completed, result=result)

        evaluation = self.evaluation.evaluate(turn_input)
        advanced = advance_dialogue(session, self._scenario, evaluation)
        turn = next(
            item
            for item in self._scenario.dialogue_turns
            if item.turn_id == turn_input.turn_id
        )
        response = getattr(turn.responses, evaluation.answer_category)
        return PracticeStep(
            session=advanced,
            evaluation=evaluation,
            dialogue_response=response,
        )
