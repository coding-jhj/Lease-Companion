"""계약 연습 시나리오 로딩, AI 평가, 상태 전이, 영속 저장 오케스트레이션."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import logging
import os
from pathlib import Path
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lease_companion_ai.providers.gemini_practice import build_practice_provider
from lease_companion_ai.providers.gemini_practice_dialogue import (
    build_practice_dialogue_provider,
)
from lease_companion_ai.rag.service import get_default_evidence_service
from lease_companion_ai.schemas.simulation import (
    DialogueTurn,
    PracticeResult,
    PracticeSessionState,
    PracticeTurnInput,
    ScenarioDefinition,
    SelectedAction,
)
from lease_companion_ai.schemas.unified import OfficialSource
from lease_companion_ai.simulation.evidence import retrieve_action_evidence
from lease_companion_ai.simulation.models import PracticeAnswerKey, load_practice_assets
from lease_companion_ai.simulation.service import PracticeSimulationService
from lease_companion_ai.simulation.state_machine import advance_dialogue_without_confirmation

from app.models.practice import PracticeSession, PracticeTurn
from app.models.user import User
from app.schemas.practice import (
    PracticeConversationPage,
    PracticeConversationTurn,
    PracticeDialogueTurnView,
    PracticeScenarioDetail,
    PracticeScenarioSummary,
    PracticeSessionResponse,
)

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRACTICE_ROOT = _REPO_ROOT / "data" / "sample" / "practice-scenarios"
APPROVED_SCENARIO_IDS = (
    "PRACTICE-DEFERRED-REFUND-001",
    "PRACTICE-THIRD-PARTY-PAYMENT-001",
    "PRACTICE-PROXY-AUTHORITY-001",
)


class PracticeServiceError(ValueError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@lru_cache(maxsize=len(APPROVED_SCENARIO_IDS))
def load_approved_practice_assets(
    scenario_id: str,
) -> tuple[ScenarioDefinition, PracticeAnswerKey]:
    if scenario_id not in APPROVED_SCENARIO_IDS:
        raise PracticeServiceError("practice_scenario_not_found", "승인된 연습 시나리오를 찾을 수 없습니다.", 404)
    scenario_dir = _PRACTICE_ROOT / scenario_id
    return load_practice_assets(scenario_dir / "scenario.json", scenario_dir / "answer-key.json")


def list_practice_scenarios() -> list[PracticeScenarioSummary]:
    return [_scenario_summary(load_approved_practice_assets(scenario_id)[0]) for scenario_id in APPROVED_SCENARIO_IDS]


def get_practice_scenario(scenario_id: str) -> PracticeScenarioDetail:
    scenario, _ = load_approved_practice_assets(scenario_id)
    first_turn = scenario.dialogue_turns[0]
    return PracticeScenarioDetail(
        **_scenario_summary(scenario).model_dump(),
        synthetic_contract=scenario.synthetic_contract,
        initial_turn=_turn_view(first_turn),
    )


def create_practice_session(db: Session, user: User, scenario_id: str) -> PracticeSession:
    scenario, answer_key = load_approved_practice_assets(scenario_id)
    service = PracticeSimulationService(scenario, answer_key)
    started_at = datetime.now(timezone.utc)
    state = service.start_session(uuid.uuid4().hex, user.id, started_at)
    row = PracticeSession(
        practice_session_id=state.session_id,
        user_id=user.id,
        scenario_id=state.scenario_id,
        scenario_version=state.scenario_version,
        status=state.status,
        current_state=state.current_state,
        current_turn_id=state.current_state,
        confirmed_action_ids=list(state.confirmed_action_ids),
        state_payload=state.model_dump(mode="json"),
        started_at=started_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_owned_practice_session(db: Session, user: User, practice_session_id: str) -> PracticeSession:
    row = db.scalar(
        select(PracticeSession).where(
            PracticeSession.practice_session_id == practice_session_id,
            PracticeSession.user_id == user.id,
        )
    )
    if row is None:
        raise PracticeServiceError("practice_session_not_found", "연습 세션을 찾을 수 없습니다.", 404)
    return row


def list_practice_conversation(
    db: Session,
    session_row: PracticeSession,
    *,
    before: str | None,
    limit: int,
) -> PracticeConversationPage:
    scenario, _ = load_approved_practice_assets(session_row.scenario_id)
    prompts = {turn.turn_id: turn.prompt for turn in scenario.dialogue_turns}
    query = (
        select(PracticeTurn)
        .where(
            PracticeTurn.practice_session_fk == session_row.id,
            PracticeTurn.turn_id.like("TURN-%"),
            PracticeTurn.dialogue_response.is_not(None),
        )
        .order_by(PracticeTurn.id.desc())
    )
    if before is not None:
        cursor_row = db.scalar(
            select(PracticeTurn).where(
                PracticeTurn.practice_session_fk == session_row.id,
                PracticeTurn.practice_turn_id == before,
            )
        )
        if cursor_row is None:
            raise PracticeServiceError("invalid_practice_cursor", "대화 기록 위치를 확인할 수 없습니다.", 400)
        query = query.where(PracticeTurn.id < cursor_row.id)

    rows = list(db.scalars(query.limit(limit + 1)))
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [
        PracticeConversationTurn(
            practice_turn_id=row.practice_turn_id,
            turn_id=row.turn_id,
            prompt=prompts.get(row.turn_id, ""),
            user_answer=row.input_payload.get("user_answer"),
            timed_out=bool(row.input_payload.get("timed_out", False)),
            dialogue_response=row.dialogue_response,
            created_at=row.created_at,
        )
        for row in reversed(page_rows)
    ]
    return PracticeConversationPage(
        items=items,
        next_cursor=page_rows[-1].practice_turn_id if has_more and page_rows else None,
        has_more=has_more,
    )


def submit_practice_turn(
    db: Session,
    session_row: PracticeSession,
    *,
    request_id: str,
    turn_id: str,
    user_answer: str | None,
    timed_out: bool,
    response_time_seconds: float,
) -> tuple[PracticeTurn, PracticeSessionState]:
    turn_input = PracticeTurnInput(
        session_id=session_row.practice_session_id,
        turn_id=turn_id,
        user_answer=user_answer,
        timed_out=timed_out,
        response_time_seconds=response_time_seconds,
    )
    return _submit(db, session_row, request_id=request_id, turn_input=turn_input)


def submit_practice_final_action(
    db: Session,
    session_row: PracticeSession,
    *,
    request_id: str,
    selected_action: SelectedAction,
    response_time_seconds: float,
) -> tuple[PracticeTurn, PracticeSessionState, PracticeResult]:
    turn_input = PracticeTurnInput(
        session_id=session_row.practice_session_id,
        turn_id="ACTION-SELECTION",
        selected_action=selected_action,
        response_time_seconds=response_time_seconds,
    )
    turn, state = _submit(
        db,
        session_row,
        request_id=request_id,
        turn_input=turn_input,
        include_result=True,
    )
    if session_row.result is None:
        raise RuntimeError("완료된 연습 세션에 결과가 저장되지 않았습니다.")
    return turn, state, PracticeResult.model_validate(session_row.result)


def advance_practice_dialogue(
    db: Session,
    session_row: PracticeSession,
    *,
    request_id: str,
    turn_id: str,
    destination: str,
) -> PracticeTurn:
    duplicate = db.scalar(
        select(PracticeTurn).where(
            PracticeTurn.practice_session_fk == session_row.id,
            PracticeTurn.request_id == request_id,
        )
    )
    if duplicate is not None:
        raise PracticeServiceError("duplicate_practice_request", "이미 처리된 연습 요청입니다.", 409)

    scenario, _ = load_approved_practice_assets(session_row.scenario_id)
    state = PracticeSessionState.model_validate(session_row.state_payload)
    try:
        advanced = advance_dialogue_without_confirmation(
            state,
            scenario,
            turn_id,
            to_action_selection=destination == "action_selection",
        )
    except ValueError as exc:
        raise PracticeServiceError("invalid_practice_transition", str(exc), 409) from exc

    attempt_no = (
        db.scalar(
            select(func.count())
            .select_from(PracticeTurn)
            .where(
                PracticeTurn.practice_session_fk == session_row.id,
                PracticeTurn.turn_id == turn_id,
            )
        )
        or 0
    ) + 1
    turn = PracticeTurn(
        practice_turn_id=uuid.uuid4().hex,
        practice_session_fk=session_row.id,
        turn_id=turn_id,
        attempt_no=attempt_no,
        request_id=request_id,
        input_payload={"turn_id": turn_id, "destination": destination},
        evaluation_payload=None,
        dialogue_response=None,
    )
    _apply_state(session_row, advanced, None)
    db.add(turn)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PracticeServiceError("duplicate_practice_request", "이미 처리된 연습 요청입니다.", 409) from exc
    db.refresh(turn)
    db.refresh(session_row)
    return turn


def session_response(row: PracticeSession) -> PracticeSessionResponse:
    scenario, _ = load_approved_practice_assets(row.scenario_id)
    state = PracticeSessionState.model_validate(row.state_payload)
    current_turn = next(
        (turn for turn in scenario.dialogue_turns if turn.turn_id == row.current_state),
        None,
    )
    allowed_actions = (
        list(scenario.action_selection.allowed_actions)
        if row.current_state == scenario.action_selection.state_id
        else []
    )
    return PracticeSessionResponse(
        practice_session_id=row.practice_session_id,
        scenario_id=row.scenario_id,
        scenario_version=row.scenario_version,
        status=row.status,
        current_state=row.current_state,
        current_turn=_turn_view(current_turn) if current_turn is not None else None,
        confirmed_action_ids=list(state.confirmed_action_ids),
        selected_action=state.selected_action,
        allowed_final_actions=allowed_actions,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _submit(
    db: Session,
    session_row: PracticeSession,
    *,
    request_id: str,
    turn_input: PracticeTurnInput,
    include_result: bool = False,
) -> tuple[PracticeTurn, PracticeSessionState]:
    duplicate = db.scalar(
        select(PracticeTurn).where(
            PracticeTurn.practice_session_fk == session_row.id,
            PracticeTurn.request_id == request_id,
        )
    )
    if duplicate is not None:
        raise PracticeServiceError("duplicate_practice_request", "이미 처리된 연습 요청입니다.", 409)

    scenario, answer_key = load_approved_practice_assets(session_row.scenario_id)
    offline_mode = os.getenv("PRACTICE_OFFLINE_MODE", "true").lower() == "true"
    provider = build_practice_provider(scenario, answer_key, offline_mode=offline_mode)
    dialogue_provider = build_practice_dialogue_provider(
        scenario, offline_mode=offline_mode
    )
    service = PracticeSimulationService(
        scenario,
        answer_key,
        provider,
        dialogue_provider=dialogue_provider,
    )
    state = PracticeSessionState.model_validate(session_row.state_payload)
    evidence_by_action = _retrieve_evidence_by_action(scenario, service) if include_result else None
    try:
        step = service.submit(
            state,
            turn_input,
            occurred_at=datetime.now(timezone.utc),
            evidence_by_action=evidence_by_action,
        )
    except ValueError as exc:
        raise PracticeServiceError("invalid_practice_transition", str(exc), 409) from exc

    attempt_no = (
        db.scalar(
            select(func.count())
            .select_from(PracticeTurn)
            .where(
                PracticeTurn.practice_session_fk == session_row.id,
                PracticeTurn.turn_id == turn_input.turn_id,
            )
        )
        or 0
    ) + 1
    turn = PracticeTurn(
        practice_turn_id=uuid.uuid4().hex,
        practice_session_fk=session_row.id,
        turn_id=turn_input.turn_id,
        attempt_no=attempt_no,
        request_id=request_id,
        input_payload=turn_input.model_dump(mode="json"),
        evaluation_payload=(step.evaluation.model_dump(mode="json") if step.evaluation is not None else None),
        dialogue_generation_payload=(
            step.dialogue_generation.model_dump(mode="json")
            if step.dialogue_generation is not None
            else None
        ),
        dialogue_response=step.dialogue_response,
    )
    _apply_state(session_row, step.session, step.result)
    db.add(turn)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PracticeServiceError("duplicate_practice_request", "이미 처리된 연습 요청입니다.", 409) from exc
    db.refresh(turn)
    db.refresh(session_row)
    return turn, step.session


def _apply_state(
    row: PracticeSession,
    state: PracticeSessionState,
    result: PracticeResult | None,
) -> None:
    row.status = state.status
    row.current_state = state.current_state
    row.current_turn_id = state.current_state if state.current_state.startswith("TURN-") else None
    row.confirmed_action_ids = list(state.confirmed_action_ids)
    row.selected_action = state.selected_action
    row.state_payload = state.model_dump(mode="json")
    row.completed_at = state.completed_at
    if result is not None:
        row.result = result.model_dump(mode="json")


def _retrieve_evidence_by_action(
    scenario: ScenarioDefinition, service: PracticeSimulationService
) -> dict[str, tuple[OfficialSource, ...]]:
    try:
        evidence_service = get_default_evidence_service()
        return {
            action.action_id: retrieve_action_evidence(
                scenario,
                action.action_id,
                service.evaluation.rule_results,
                evidence_service,
            )
            for action in scenario.target_actions
        }
    except Exception:
        logger.warning(
            "연습 복기 공식 근거 검색에 실패해 빈 근거로 계속합니다.",
            exc_info=True,
        )
        return {}


def _scenario_summary(scenario: ScenarioDefinition) -> PracticeScenarioSummary:
    return PracticeScenarioSummary(
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.scenario_version,
        title=scenario.title,
        role=scenario.role,
        difficulty=scenario.difficulty,
        contract_stage=scenario.contract_stage,
        always_show_labels=list(scenario.always_show_labels),
    )


def _turn_view(turn: DialogueTurn) -> PracticeDialogueTurnView:
    return PracticeDialogueTurnView(
        turn_id=turn.turn_id,
        prompt=turn.prompt,
        wait_sequence=list(turn.wait_sequence),
    )
