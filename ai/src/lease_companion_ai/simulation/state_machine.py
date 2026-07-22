"""연습 세션의 결정적 상태 전이와 누적 행동 상태."""

from __future__ import annotations

from datetime import datetime

from lease_companion_ai.schemas.simulation import (
    PracticeSessionState,
    PracticeTurnEvaluation,
    PracticeTurnInput,
    ScenarioDefinition,
    VerbalReliance,
    VerbalRelianceObservation,
    allowed_next_dialogue_states,
)


def start_practice_session(
    scenario: ScenarioDefinition,
    session_id: str,
    user_id: int,
    started_at: datetime,
) -> PracticeSessionState:
    return PracticeSessionState(
        session_id=session_id,
        user_id=user_id,
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.scenario_version,
        current_state=scenario.dialogue_turns[0].turn_id,
        started_at=started_at,
        status="active",
    )


def validate_session(
    session: PracticeSessionState,
    scenario: ScenarioDefinition,
    turn_input: PracticeTurnInput,
) -> None:
    if session.scenario_id != scenario.scenario_id:
        raise ValueError("세션과 시나리오 ID가 일치하지 않습니다.")
    if session.scenario_version != scenario.scenario_version:
        raise ValueError("세션과 시나리오 버전이 일치하지 않습니다.")
    if turn_input.session_id != session.session_id:
        raise ValueError("세션 ID가 일치하지 않습니다.")
    if session.status != "active":
        raise ValueError("완료되거나 중단된 세션에는 입력할 수 없습니다.")
    if turn_input.turn_id != session.current_state:
        raise ValueError("입력 turn_id가 현재 상태와 일치하지 않습니다.")


def advance_dialogue(
    session: PracticeSessionState,
    scenario: ScenarioDefinition,
    evaluation: PracticeTurnEvaluation,
) -> PracticeSessionState:
    turn = next(
        (item for item in scenario.dialogue_turns if item.turn_id == session.current_state),
        None,
    )
    if turn is None or evaluation.turn_id != turn.turn_id:
        raise ValueError("평가 turn_id가 현재 대화 상태와 일치하지 않습니다.")
    # 진행 여부는 분류별 허용 전이 안에서 평가(LLM)가 상황에 맞게 정한다.
    # appropriate_check는 진행 고정, 회피·무응답·검토불가는 재시도 고정,
    # partial_check·ambiguous_answer는 진행/재시도 모두 허용한다.
    allowed = allowed_next_dialogue_states(
        evaluation.answer_category, turn.next_turn_id, turn.turn_id
    )
    if evaluation.next_dialogue_state not in allowed:
        raise ValueError("평가의 다음 상태가 허용된 전이가 아닙니다.")
    expected_state = evaluation.next_dialogue_state

    action_by_id = {action.action_id: action for action in scenario.target_actions}
    confirmed_action_ids = list(
        dict.fromkeys(
            [
                *session.confirmed_action_ids,
                *evaluation.confirmed_action_ids,
            ]
        )
    )
    newly_confirmed = [
        action_by_id[action_id]
        for action_id in evaluation.confirmed_action_ids
        if action_id not in session.confirmed_action_ids
    ]
    recognized_signal_ids = list(
        dict.fromkeys(
            [
                *session.recognized_signal_ids,
                *(
                    signal_id
                    for action in newly_confirmed
                    for signal_id in action.linked_signal_ids
                ),
            ]
        )
    )
    effects = {
        effect
        for action in newly_confirmed
        for effect in action.effect_tags
    }
    evidence_texts = list(session.evidence_texts)
    if (
        evaluation.evidence_text is not None
        and evaluation.evidence_text not in evidence_texts
    ):
        evidence_texts.append(evaluation.evidence_text)
    no_response_counts = dict(session.no_response_counts)
    if evaluation.answer_category == "no_response":
        no_response_counts[turn.turn_id] = no_response_counts.get(turn.turn_id, 0) + 1

    payload = session.model_dump(mode="python")
    payload.update(
        current_state=expected_state,
        evaluations=[*session.evaluations, evaluation],
        confirmed_action_ids=confirmed_action_ids,
        recognized_signal_ids=recognized_signal_ids,
        verbal_reliance=_merge_verbal_reliance(
            session.verbal_reliance, evaluation.verbal_reliance
        ),
        document_or_clause_requested=(
            session.document_or_clause_requested
            or "document_or_clause_request" in effects
        ),
        contract_or_signing_held=(
            session.contract_or_signing_held
            or "contract_or_signing_hold" in effects
        ),
        payment_held=session.payment_held or "payment_hold" in effects,
        evidence_texts=evidence_texts,
        no_response_counts=no_response_counts,
    )
    return PracticeSessionState.model_validate(payload)


def complete_action_selection(
    session: PracticeSessionState,
    scenario: ScenarioDefinition,
    turn_input: PracticeTurnInput,
    completed_at: datetime,
) -> PracticeSessionState:
    if session.current_state != scenario.action_selection.state_id:
        raise ValueError("최종 행동 선택은 현재 상태에서 허용되지 않습니다.")
    selected_action = turn_input.selected_action
    if selected_action not in scenario.action_selection.allowed_actions:
        raise ValueError("시나리오에서 허용하지 않는 최종 행동입니다.")
    payload = session.model_dump(mode="python")
    payload.update(
        current_state=scenario.terminal_state_id,
        status="completed",
        completed_at=completed_at,
        selected_action=selected_action,
    )
    return PracticeSessionState.model_validate(payload)


def _merge_verbal_reliance(
    current: VerbalReliance,
    observation: VerbalRelianceObservation,
) -> VerbalReliance:
    if observation == "not_observed":
        return current
    if current == "not_observed":
        return observation
    if current == observation:
        return current
    return "mixed"
