"""연습 턴 평가와 안전 fallback을 조정한다."""

from __future__ import annotations

from copy import deepcopy

from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderResponseValidationError,
)
from lease_companion_ai.schemas.minimum_mvp import RuleResult
from lease_companion_ai.schemas.simulation import (
    PracticeTurnEvaluation,
    PracticeTurnInput,
    ScenarioDefinition,
)
from lease_companion_ai.schemas.unified import RuleStatus, Urgency
from lease_companion_ai.simulation.models import PracticeAnswerKey
from lease_companion_ai.simulation.provider import (
    PRACTICE_PROMPT_VERSION,
    PracticeAnswerProvider,
    PracticeEvaluationRequest,
    PracticeRuleState,
    validate_provider_result,
)
from lease_companion_ai.simulation.rules import run_practice_rules


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
            return self._fallback(turn.turn_id, "provider_unavailable")

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
        )
        before = self._rule_fingerprint(request.rule_states)
        try:
            result = self._provider.classify(request)
        except TimeoutError:
            return self._fallback(turn.turn_id, "provider_timeout")
        except ProviderResponseValidationError:
            return self._fallback(turn.turn_id, "response_validation_failed")
        except ProviderError:
            return self._fallback(turn.turn_id, "provider_error")
        except Exception:
            return self._fallback(turn.turn_id, "provider_error")
        if self._rule_fingerprint(request.rule_states) != before:
            return self._fallback(turn.turn_id, "rule_mutation")
        try:
            return validate_provider_result(request, result)
        except ProviderResponseValidationError:
            return self._fallback(turn.turn_id, "response_validation_failed")

    @staticmethod
    def _rule_fingerprint(
        states: tuple[PracticeRuleState, ...]
    ) -> tuple[tuple[str, RuleStatus, Urgency], ...]:
        return tuple((item.rule_id, item.status, item.urgency) for item in states)

    @staticmethod
    def _fallback(turn_id: str, reason: str) -> PracticeTurnEvaluation:
        return PracticeTurnEvaluation(
            turn_id=turn_id,
            answer_category="needs_review",
            confirmed_action_ids=[],
            next_dialogue_state=turn_id,
            fallback_reason=reason,
        )
