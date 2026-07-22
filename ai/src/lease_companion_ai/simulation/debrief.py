"""연습 평가를 점수 없는 복기 결과로 구성하고 저장 전 검증한다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from lease_companion_ai.guardrails.prohibited_claims import has_prohibited_claim
from lease_companion_ai.schemas.simulation import (
    PracticeResult,
    PracticeTurnEvaluation,
    ScenarioDefinition,
    SelectedAction,
)
from lease_companion_ai.schemas.unified import OfficialSource
from lease_companion_ai.simulation.models import PracticeAnswerKey


class PracticeGuardrailBlocked(ValueError):
    pass


def build_practice_result(
    session_id: str,
    scenario: ScenarioDefinition,
    answer_key: PracticeAnswerKey,
    evaluations: Sequence[PracticeTurnEvaluation],
    evidence_by_action: Mapping[str, Sequence[OfficialSource]],
    *,
    selected_action: SelectedAction | None = None,
) -> PracticeResult:
    """승인 근거와 안전 문구만 포함한 복기 결과를 반환한다."""

    action_by_id = {item.action_id: item for item in scenario.target_actions}
    signal_by_id = {
        item.signal_id: item for item in scenario.hidden_confirmation_signals
    }
    allowed_by_action = {
        action.action_id: {
            source_id
            for signal_id in action.linked_signal_ids
            for source_id in signal_by_id[signal_id].official_source_ids
        }
        & set(answer_key.debrief.official_source_ids)
        for action in scenario.target_actions
    }
    source_ids: list[str] = []
    for action_id, sources in evidence_by_action.items():
        if action_id not in action_by_id:
            raise PracticeGuardrailBlocked("unapproved_action")
        for source in sources:
            if source.source_id not in allowed_by_action[action_id]:
                raise PracticeGuardrailBlocked("unapproved_source")
            if source.source_id not in source_ids:
                source_ids.append(source.source_id)

    confirmed_ids = list(
        dict.fromkeys(
            action_id
            for evaluation in evaluations
            for action_id in evaluation.confirmed_action_ids
        )
    )
    if any(action_id not in action_by_id for action_id in confirmed_ids):
        raise PracticeGuardrailBlocked("unapproved_action")
    missed_ids = [
        action.action_id
        for action in scenario.target_actions
        if action.action_id not in confirmed_ids
    ]
    confirmed_actions = [action_by_id[action_id].name for action_id in confirmed_ids]
    missed_signals = list(
        dict.fromkeys(
            signal_by_id[signal_id].fact
            for action_id in missed_ids
            for signal_id in action_by_id[action_id].linked_signal_ids
        )
    )
    texts = (
        *confirmed_actions,
        *missed_signals,
        *answer_key.debrief.recommended_phrases,
        *answer_key.debrief.next_actions,
    )
    if has_prohibited_claim(texts) or any(
        forbidden in text
        for forbidden in answer_key.debrief.forbidden_conclusions
        for text in texts
    ):
        raise PracticeGuardrailBlocked("prohibited_claim")

    return PracticeResult(
        session_id=session_id,
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.scenario_version,
        selected_action=selected_action,
        confirmed_action_ids=confirmed_ids,
        missed_action_ids=missed_ids,
        confirmed_actions=confirmed_actions,
        missed_signals=missed_signals,
        recommended_phrases=list(answer_key.debrief.recommended_phrases),
        next_actions=list(answer_key.debrief.next_actions),
        official_source_ids=source_ids,
    )
