from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lease_companion_ai.schemas.simulation import (
    PracticeTurnEvaluation,
    PracticeTurnInput,
)
from lease_companion_ai.simulation.models import load_practice_assets
from lease_companion_ai.simulation.service import PracticeSimulationService


ROOT = Path(__file__).resolve().parents[3]
PRACTICE_ROOT = ROOT / "data" / "sample" / "practice-scenarios"
SCENARIO_IDS = (
    "PRACTICE-DEFERRED-REFUND-001",
    "PRACTICE-THIRD-PARTY-PAYMENT-001",
    "PRACTICE-PROXY-AUTHORITY-001",
)
STARTED_AT = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)


def _assets(scenario_id: str):
    directory = PRACTICE_ROOT / scenario_id
    return load_practice_assets(
        directory / "scenario.json",
        directory / "answer-key.json",
    )


EXAMPLE_CASES = []
for _scenario_id in SCENARIO_IDS:
    _scenario, _answer_key = _assets(_scenario_id)
    for _example in _answer_key.evaluation_examples:
        EXAMPLE_CASES.append((_scenario, _answer_key, _example))


class ExampleProvider:
    model_name = "answer-key-example-v1"

    def __init__(self, example) -> None:
        self.example = example
        self.calls = 0

    def classify(self, request):
        self.calls += 1
        if self.example.input_context.provider_error == "timeout":
            raise TimeoutError
        fallback_reason = (
            "conflicting_semantics"
            if self.example.expected_status_id == "needs_review"
            else None
        )
        return PracticeTurnEvaluation(
            turn_id=request.turn_id,
            answer_category=self.example.expected_status_id,
            confirmed_action_ids=list(self.example.expected_confirmed_action_ids),
            next_dialogue_state=self.example.expected_next_turn_id,
            fallback_reason=fallback_reason,
            evidence_text="provider가 만든 근거는 저장하면 안 됩니다.",
        )


@pytest.mark.parametrize(
    "scenario,answer_key,example",
    EXAMPLE_CASES,
    ids=[
        f"{scenario.scenario_id}:{example.example_id}"
        for scenario, _, example in EXAMPLE_CASES
    ],
)
def test_all_three_scenario_examples_use_the_common_evaluation_service(
    scenario, answer_key, example
):
    provider = ExampleProvider(example)
    service = PracticeSimulationService(scenario, answer_key, provider)
    session = service.start_session("practice-session-001", 1, STARTED_AT)
    session_payload = session.model_dump(mode="python")
    session_payload["current_state"] = example.turn_id
    session = type(session).model_validate(session_payload)
    timed_out = example.expected_status_id == "no_response"
    turn_input = PracticeTurnInput(
        session_id="practice-session-001",
        turn_id=example.turn_id,
        user_answer=None if timed_out else example.user_input,
        timed_out=timed_out,
        response_time_seconds=example.input_context.elapsed_seconds or 0,
    )

    step = service.submit(session, turn_input, occurred_at=STARTED_AT)
    evaluation = step.evaluation

    assert evaluation is not None
    assert evaluation.answer_category == example.expected_status_id
    assert evaluation.confirmed_action_ids == list(
        example.expected_confirmed_action_ids
    )
    assert evaluation.next_dialogue_state == example.expected_next_turn_id
    assert evaluation.evidence_text == (None if timed_out else example.user_input)
    assert step.session.current_state == example.expected_next_turn_id
    assert provider.calls == (0 if timed_out else 1)


class TurnProvider:
    model_name = "turn-provider-v1"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def classify(self, request):
        if self.fail:
            raise TimeoutError
        return PracticeTurnEvaluation(
            turn_id=request.turn_id,
            answer_category="appropriate_check",
            confirmed_action_ids=[request.goal_action_id],
            next_dialogue_state=request.success_next_state,
            verbal_reliance="rejected",
            evidence_text="provider 생성 문장",
        )


def _turn(session_id: str, turn_id: str, answer: str) -> PracticeTurnInput:
    return PracticeTurnInput(
        session_id=session_id,
        turn_id=turn_id,
        user_answer=answer,
        response_time_seconds=2,
    )


def test_session_accumulates_actions_signals_effects_and_completes_debrief():
    scenario, answer_key = _assets("PRACTICE-DEFERRED-REFUND-001")
    service = PracticeSimulationService(scenario, answer_key, TurnProvider())
    session = service.start_session("practice-session-001", 7, STARTED_AT)

    first = service.submit(
        session,
        _turn(session.session_id, "TURN-01", "후임 임차인 입주 조건인지 확인합니다."),
        occurred_at=STARTED_AT,
    )
    second = service.submit(
        first.session,
        _turn(session.session_id, "TURN-02", "구두 설명 대신 특약을 수정해 주세요."),
        occurred_at=STARTED_AT,
    )
    third = service.submit(
        second.session,
        _turn(session.session_id, "TURN-03", "수정 전에는 계약을 보류하겠습니다."),
        occurred_at=STARTED_AT,
    )

    assert third.session.current_state == "ACTION-SELECTION"
    assert third.session.confirmed_action_ids == ["PA01", "PA02", "PA03"]
    assert third.session.recognized_signal_ids == ["SIG-DEFERRED-REFUND"]
    assert third.session.verbal_reliance == "rejected"
    assert third.session.document_or_clause_requested is True
    assert third.session.contract_or_signing_held is True
    assert third.session.payment_held is False
    assert third.session.evidence_texts == [
        "후임 임차인 입주 조건인지 확인합니다.",
        "구두 설명 대신 특약을 수정해 주세요.",
        "수정 전에는 계약을 보류하겠습니다.",
    ]

    completed = service.submit(
        third.session,
        PracticeTurnInput(
            session_id=session.session_id,
            turn_id="ACTION-SELECTION",
            selected_action="보류",
            response_time_seconds=1,
        ),
        occurred_at=STARTED_AT,
    )

    assert completed.session.status == "completed"
    assert completed.session.current_state == "DEBRIEF"
    assert completed.session.selected_action == "보류"
    assert completed.result is not None
    assert completed.result.selected_action == "보류"
    assert completed.result.missed_action_ids == []


def test_provider_failure_keeps_turn_and_is_not_recorded_as_user_error():
    scenario, answer_key = _assets("PRACTICE-PROXY-AUTHORITY-001")
    service = PracticeSimulationService(scenario, answer_key, TurnProvider(fail=True))
    session = service.start_session("practice-session-002", 8, STARTED_AT)

    step = service.submit(
        session,
        _turn(session.session_id, "TURN-01", "소유자 확인 후 진행하겠습니다."),
        occurred_at=STARTED_AT,
    )

    assert step.session.current_state == "TURN-01"
    assert step.session.confirmed_action_ids == []
    assert step.evaluation is not None
    assert step.evaluation.answer_category == "needs_review"
    assert step.evaluation.fallback_reason == "provider_timeout"
    assert step.evaluation.evidence_text == "소유자 확인 후 진행하겠습니다."


def test_provider_cannot_mutate_judgment_state():
    scenario, answer_key = _assets("PRACTICE-DEFERRED-REFUND-001")

    class MutatingJudgmentProvider(TurnProvider):
        def classify(self, request):
            object.__setattr__(request.judgment_states[0], "status", "명확")
            return super().classify(request)

    service = PracticeSimulationService(
        scenario, answer_key, MutatingJudgmentProvider()
    )
    session = service.start_session("practice-session-005", 11, STARTED_AT)

    step = service.submit(
        session,
        _turn(session.session_id, "TURN-01", "반환 조건을 확인하겠습니다."),
        occurred_at=STARTED_AT,
    )

    assert step.evaluation is not None
    assert step.evaluation.answer_category == "needs_review"
    assert step.evaluation.fallback_reason == "rule_mutation"
    assert step.session.current_state == "TURN-01"


def test_no_response_count_and_transition_are_deterministic():
    scenario, answer_key = _assets("PRACTICE-THIRD-PARTY-PAYMENT-001")
    service = PracticeSimulationService(scenario, answer_key, TurnProvider())
    session = service.start_session("practice-session-003", 9, STARTED_AT)
    timed_out = PracticeTurnInput(
        session_id=session.session_id,
        turn_id="TURN-01",
        timed_out=True,
        response_time_seconds=10,
    )

    first = service.submit(session, timed_out, occurred_at=STARTED_AT)
    repeated = service.submit(session, timed_out, occurred_at=STARTED_AT)

    assert first == repeated
    assert first.session.current_state == "TURN-01"
    assert first.session.no_response_counts == {"TURN-01": 1}
    assert first.evaluation is not None
    assert first.evaluation.answer_category == "no_response"


def test_action_selection_is_rejected_before_dialogue_completion():
    scenario, answer_key = _assets("PRACTICE-THIRD-PARTY-PAYMENT-001")
    service = PracticeSimulationService(scenario, answer_key, TurnProvider())
    session = service.start_session("practice-session-004", 10, STARTED_AT)

    with pytest.raises(ValueError, match="현재 상태"):
        service.submit(
            session,
            PracticeTurnInput(
                session_id=session.session_id,
                turn_id="ACTION-SELECTION",
                selected_action="보류",
                response_time_seconds=1,
            ),
            occurred_at=STARTED_AT,
        )


# --- 진행 정책: 목표문장이 아니어도 상황에 맞으면 진행 (LLM 판단) ---

from lease_companion_ai.schemas.simulation import allowed_next_dialogue_states
from lease_companion_ai.simulation.state_machine import (
    advance_dialogue,
    start_practice_session,
)


def _first_turn_eval(scenario, category, *, advance: bool):
    turn = scenario.dialogue_turns[0]
    return turn, PracticeTurnEvaluation(
        turn_id=turn.turn_id,
        answer_category=category,
        confirmed_action_ids=[],
        next_dialogue_state=turn.next_turn_id if advance else turn.turn_id,
    )


def test_policy_allows_partial_and_ambiguous_to_advance_or_retry():
    assert allowed_next_dialogue_states("appropriate_check", "TURN-02", "TURN-01") == {"TURN-02"}
    assert allowed_next_dialogue_states("avoidance", "TURN-02", "TURN-01") == {"TURN-01"}
    assert allowed_next_dialogue_states("no_response", "TURN-02", "TURN-01") == {"TURN-01"}
    assert allowed_next_dialogue_states("partial_check", "TURN-02", "TURN-01") == {"TURN-01", "TURN-02"}
    assert allowed_next_dialogue_states("ambiguous_answer", "TURN-02", "TURN-01") == {"TURN-01", "TURN-02"}


def test_partial_check_can_advance_to_next_turn():
    scenario, _ = _assets("PRACTICE-DEFERRED-REFUND-001")
    session = start_practice_session(scenario, "S-ADV", 1, STARTED_AT)
    turn, evaluation = _first_turn_eval(scenario, "partial_check", advance=True)

    advanced = advance_dialogue(session, scenario, evaluation)

    assert advanced.current_state == turn.next_turn_id  # 목표문장 없어도 진행


def test_partial_check_may_still_retry_same_turn():
    scenario, _ = _assets("PRACTICE-DEFERRED-REFUND-001")
    session = start_practice_session(scenario, "S-RETRY", 1, STARTED_AT)
    turn, evaluation = _first_turn_eval(scenario, "partial_check", advance=False)

    advanced = advance_dialogue(session, scenario, evaluation)

    assert advanced.current_state == turn.turn_id


def test_avoidance_cannot_advance_even_if_requested():
    scenario, _ = _assets("PRACTICE-DEFERRED-REFUND-001")
    session = start_practice_session(scenario, "S-AVOID", 1, STARTED_AT)
    _, evaluation = _first_turn_eval(scenario, "avoidance", advance=True)

    with pytest.raises(ValueError, match="허용된 전이"):
        advance_dialogue(session, scenario, evaluation)
