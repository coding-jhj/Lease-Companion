"""연습 턴 평가와 안전 fallback을 조정한다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import re

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
    SelectedAction,
)
from lease_companion_ai.schemas.unified import (
    OfficialSource,
    RuleResult,
    RuleStatus,
    Urgency,
)
from lease_companion_ai.simulation.debrief import build_practice_result
from lease_companion_ai.simulation.dialogue_guardrail import (
    DialogueGuardrailViolation,
    validate_grounded_dialogue,
)
from lease_companion_ai.simulation.dialogue_planner import (
    detect_dialogue_intent,
    plan_grounded_dialogue,
)
from lease_companion_ai.simulation.dialogue_provider import (
    DialogueGenerationMetadata,
    DialogueGenerationRequest,
    PracticeDialogueProvider,
)
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
    dialogue_generation: DialogueGenerationMetadata | None = None
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
        """답변 범주와 의도를 한 번에 정한다. 의도 판별은 항상 Python이 한다."""

        return self._with_intents(self._classify(turn_input), turn_input)

    def _with_intents(
        self,
        evaluation: PracticeTurnEvaluation,
        turn_input: PracticeTurnInput,
    ) -> PracticeTurnEvaluation:
        answer = turn_input.user_answer
        if answer is None or evaluation.answer_category == "needs_review":
            # 무응답과 provider 장애는 사용자의 결정으로 읽지 않는다.
            return evaluation
        return evaluation.model_copy(
            update={
                "dialogue_intent": detect_dialogue_intent(self._scenario, answer),
                "action_intent": detect_action_intent(answer),
            }
        )

    def _classify(self, turn_input: PracticeTurnInput) -> PracticeTurnEvaluation:
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
                next_dialogue_state=turn.next_turn_id,
            )
        if turn_input.user_answer is None:
            raise ValueError("대화 턴에는 사용자 답변이 필요합니다.")
        deterministic = match_deterministic_semantic_rule(
            self._answer_key,
            turn.turn_id,
            turn.goal_action_id,
            turn.next_turn_id,
            turn_input.user_answer,
        )
        if deterministic is not None:
            return deterministic
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


def match_deterministic_semantic_rule(
    answer_key: PracticeAnswerKey,
    turn_id: str,
    goal_action_id: str,
    success_next_state: str,
    user_answer: str,
) -> PracticeTurnEvaluation | None:
    """승인 answer-key의 고신뢰 의미 묶음만 확정하고 나머지는 Gemini에 맡긴다."""

    normalized_answer = _normalize_semantic_text(user_answer)
    for rule in answer_key.deterministic_semantic_rules:
        if rule.turn_id != turn_id:
            continue
        if any(
            _normalize_semantic_text(keyword) in normalized_answer
            for keyword in rule.none_of_keywords
        ):
            continue
        if not all(
            any(
                _normalize_semantic_text(keyword) in normalized_answer
                for keyword in group
            )
            for group in rule.all_of_keyword_groups
        ):
            continue
        confirmed = (
            [goal_action_id]
            if rule.answer_category == "appropriate_check"
            else []
        )
        return PracticeTurnEvaluation(
            turn_id=turn_id,
            answer_category=rule.answer_category,
            confirmed_action_ids=confirmed,
            next_dialogue_state=success_next_state,
            evidence_text=user_answer,
        )
    return None


def _normalize_semantic_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold(), flags=re.UNICODE)


# "특약을 고쳐 주면 계약할게요"처럼 조건을 붙인 답변은 계약 진행 결정이 아니다.
# 조건 표현이 있으면 진행 의도로 읽지 않는다.
_CONDITIONAL_MARKERS: tuple[str, ...] = (
    "하면",
    "해주면",
    "해 주면",
    "된다면",
    "준다면",
    "라면",
    "조건으로",
    "조건이면",
    "경우에만",
    "고쳐야",
    "수정해야",
    "바꿔야",
    "확인하고",
    "확인한 뒤",
    "확인한 후",
)

# 앞에 있는 의도부터 확인한다. 보류를 중단보다 먼저 보는 이유는 "오늘은 결정하지
# 않겠습니다"처럼 미루는 말이 중단 표현에 먼저 걸리기 때문이다. 조건부 요구가 계약 진행
# 으로 잘못 읽히지 않도록 진행은 마지막에 판정한다.
#
# 한국어 어미 변화를 일일이 나열하지 않고 어간 기준 정규식으로 잡는다. 문자열은 비교 전에
# 공백·기호를 지우므로 패턴도 붙여 쓴 형태로 적는다.
_ACTION_INTENT_PATTERNS: tuple[tuple[SelectedAction, str], ...] = (
    (
        "보류",
        r"보류|다시생각|생각해보|생각좀|생각을더|고민해보|고민좀|미루|나중에결정"
        r"|결정하지않|결정을미루|오늘은결정|좀더알아보|더알아보|천천히결정|시간을더",
    ),
    (
        "중단",
        r"(?:계약|진행|서명|송금|입금)(?:을|를|은|는)?(?:하지않|안하|안할|못하|중단|취소|포기)"
        r"|계약중단|계약취소|그만두|그만하|안하겠|안할래|안할게|하지않겠|하지않을"
        r"|포기하|취소하|없던일|다른집을보|다른곳을보",
    ),
    (
        "특약 수정 요구",
        r"특약(?:을|를)?(?:고쳐|수정|바꿔|삭제)|조항(?:을|를)?(?:고쳐|수정|바꿔|삭제)"
        r"|문구(?:를|을)?(?:바꿔|고쳐|수정)|수정해주|고쳐주세요|삭제해주",
    ),
    (
        "추가 확인",
        r"확인해보고|확인하고결정|확인한뒤|확인한후|등기부|서류를보고|자료를받아|자료를보고",
    ),
    (
        "진행",
        r"(?:계약|진행|서명)(?:을|를)?(?:하겠|할게|할래|하죠|합시다|하시죠|진행)"
        r"|계약진행|그렇게하겠|이대로진행|이대로계약",
    ),
)


def detect_action_intent(user_answer: str) -> SelectedAction | None:
    """사용자 답변에서 계약 행동 의도를 읽는다. 판정을 바꾸지 않고 기록만 한다.

    이 값은 연습을 즉시 끝내지 않는다. 종료 여부는 사용자가 확인 화면에서 직접
    고른다. 따라서 오탐의 최대 영향은 확인 화면이 한 번 뜨는 것이다.
    """

    normalized = _normalize_semantic_text(user_answer)
    conditional = any(
        _normalize_semantic_text(marker) in normalized
        for marker in _CONDITIONAL_MARKERS
    )
    for intent, pattern in _ACTION_INTENT_PATTERNS:
        if intent == "진행" and conditional:
            # "고쳐 주면 계약할게요"는 조건부 요구이므로 진행으로 확정하지 않는다.
            continue
        if re.search(pattern, normalized):
            return intent
    return None


class PracticeSimulationService:
    """한 턴 평가를 세션 상태 전이와 최종 복기에 연결한다."""

    def __init__(
        self,
        scenario: ScenarioDefinition,
        answer_key: PracticeAnswerKey,
        provider: PracticeAnswerProvider | None = None,
        *,
        dialogue_provider: PracticeDialogueProvider | None = None,
    ) -> None:
        self._scenario = scenario
        self._answer_key = answer_key
        self._dialogue_provider = dialogue_provider
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
        dialogue_generation = None
        if (
            self._scenario.grounded_roleplay is not None
            and turn_input.user_answer is not None
        ):
            response, dialogue_generation = self._generate_grounded_dialogue(
                session,
                turn,
                turn_input,
                evaluation,
            )
            advanced = advanced.model_copy(
                update={"last_dialogue_intent": dialogue_generation.question_intent}
            )
        elif evaluation.answer_category != "appropriate_check":
            # 부족하거나 불명확한 답변에는 정답을 가르치는 변형 대사보다
            # 시나리오가 승인한 회유·진행 확인 반응을 우선한다.
            response = getattr(turn.responses, evaluation.answer_category)
        else:
            response = select_dialogue_response(
                self._answer_key,
                turn.turn_id,
                turn_input.user_answer,
                getattr(turn.responses, evaluation.answer_category),
            )
        return PracticeStep(
            session=advanced,
            evaluation=evaluation,
            dialogue_response=response,
            dialogue_generation=dialogue_generation,
        )

    def _generate_grounded_dialogue(
        self,
        session: PracticeSessionState,
        turn,
        turn_input: PracticeTurnInput,
        evaluation: PracticeTurnEvaluation,
    ) -> tuple[str, DialogueGenerationMetadata]:
        config = self._scenario.grounded_roleplay
        assert config is not None
        assert turn_input.user_answer is not None
        plan = plan_grounded_dialogue(
            self._scenario,
            turn,
            turn_input.user_answer,
            evaluation,
            previous_intent=session.last_dialogue_intent,
        )
        assert plan is not None
        facts_by_id = {fact.fact_id: fact for fact in config.approved_facts}
        approved_facts = tuple(
            facts_by_id[fact_id] for fact_id in plan.allowed_fact_ids
        )
        allowed_entities = tuple(
            value
            for value in (
                self._scenario.synthetic_contract.landlord_name,
                self._scenario.synthetic_contract.broker_name,
                *self._scenario.synthetic_contract.owner_names,
                "신규 임차인",
                "새 임차인",
                "후임 임차인",
                "보증금",
                "특약",
            )
            if value
        )
        failures: list[str] = []
        used_fact_ids: tuple[str, ...] = ()
        attempts = 0
        response: str | None = None
        fallback_used = False
        if self._dialogue_provider is not None:
            for _ in range(2):
                request = DialogueGenerationRequest(
                    prompt_version=config.prompt_version,
                    scenario_id=self._scenario.scenario_id,
                    scenario_version=self._scenario.scenario_version,
                    turn_id=turn.turn_id,
                    user_answer=turn_input.user_answer,
                    evaluation_category=evaluation.answer_category,
                    role="공인중개사",
                    approved_facts=approved_facts,
                    plan=plan,
                    allowed_entities=allowed_entities,
                    correction_codes=tuple(failures[-1:]),
                )
                attempts += 1
                try:
                    generated = self._dialogue_provider.generate(request)
                    validated = validate_grounded_dialogue(request, generated)
                    response = validated.response_text
                    used_fact_ids = validated.used_fact_ids
                    break
                except DialogueGuardrailViolation as exc:
                    failures.append(exc.code)
                except ProviderResponseValidationError:
                    failures.append("response_validation_failed")
                except (TimeoutError, ProviderError):
                    failures.append("provider_unavailable")
                    break
                except Exception:
                    failures.append("provider_error")
                    break
        if response is None:
            fallback_used = True
            fallback_options = config.fallbacks[plan.speech_act]
            prior_attempts = sum(
                item.turn_id == turn.turn_id for item in session.evaluations
            )
            response = fallback_options[prior_attempts % len(fallback_options)]
        metadata = DialogueGenerationMetadata(
            prompt_version=config.prompt_version,
            question_intent=plan.question_intent,
            speech_act=plan.speech_act,
            allowed_fact_ids=plan.allowed_fact_ids,
            used_fact_ids=used_fact_ids,
            validation_failure_codes=tuple(failures),
            generation_attempts=attempts,
            fallback_used=fallback_used,
            provider_model=(
                self._dialogue_provider.model_name
                if self._dialogue_provider is not None
                else None
            ),
        )
        return response, metadata


def select_dialogue_response(
    answer_key: PracticeAnswerKey,
    turn_id: str,
    user_answer: str | None,
    default_response: str,
) -> str:
    """평가 결과는 바꾸지 않고 사용자 질문 의도에 맞는 대사만 선택한다."""

    if not user_answer:
        return default_response
    normalized_answer = _normalize_dialogue_text(user_answer)
    for variant in answer_key.dialogue_response_variants:
        if variant.turn_id != turn_id:
            continue
        if all(
            any(_normalize_dialogue_text(keyword) in normalized_answer for keyword in group)
            for group in variant.keyword_groups
        ):
            return variant.response
    return default_response


def _normalize_dialogue_text(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())
