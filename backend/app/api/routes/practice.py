"""승인된 계약 연습 시나리오·세션·턴·복기 API."""

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from lease_companion_ai.schemas.simulation import PracticeResult, PracticeTurnEvaluation

from app.api.dependencies.auth import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.practice import (
    PracticeConversationPage,
    PracticeFinalActionRequest,
    PracticeMediaJobResponse,
    PracticeAdvanceRequest,
    PracticeResultResponse,
    PracticeScenarioDetail,
    PracticeScenarioSummary,
    PracticeSessionCreateRequest,
    PracticeSessionResponse,
    PracticeTurnRequest,
    PracticeTurnResponse,
)
from app.services.practice import (
    PracticeServiceError,
    create_practice_session,
    get_owned_practice_session,
    get_practice_scenario,
    list_practice_conversation,
    list_practice_scenarios,
    session_response,
    submit_practice_final_action,
    submit_practice_turn,
    advance_practice_dialogue,
)
from app.services.practice_media import (
    get_latest_practice_media_job,
    get_owned_practice_media_job,
    media_job_response,
    queue_practice_media_job,
    resolve_media_file,
)
from app.workers.practice_media import launch_practice_media_job

router = APIRouter(tags=["practice"])


def _raise_http(exc: PracticeServiceError) -> NoReturn:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    ) from exc


@router.get("/api/practice-scenarios", response_model=list[PracticeScenarioSummary])
def list_scenarios(
    user: User = Depends(get_current_user),
) -> list[PracticeScenarioSummary]:
    del user
    return list_practice_scenarios()


@router.get("/api/practice-scenarios/{scenario_id}", response_model=PracticeScenarioDetail)
def get_scenario(
    scenario_id: str,
    user: User = Depends(get_current_user),
) -> PracticeScenarioDetail:
    del user
    try:
        return get_practice_scenario(scenario_id)
    except PracticeServiceError as exc:
        _raise_http(exc)


@router.post("/api/practice-sessions", status_code=201, response_model=PracticeSessionResponse)
def start_session(
    body: PracticeSessionCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticeSessionResponse:
    try:
        row = create_practice_session(db, user, body.scenario_id)
        return session_response(row)
    except PracticeServiceError as exc:
        _raise_http(exc)


@router.get(
    "/api/practice-sessions/{practice_session_id}",
    response_model=PracticeSessionResponse,
)
def get_session(
    practice_session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticeSessionResponse:
    try:
        return session_response(get_owned_practice_session(db, user, practice_session_id))
    except PracticeServiceError as exc:
        _raise_http(exc)


@router.get(
    "/api/practice-sessions/{practice_session_id}/media/latest",
    response_model=PracticeMediaJobResponse | None,
)
def get_latest_session_media(
    practice_session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticeMediaJobResponse | None:
    try:
        session_row = get_owned_practice_session(db, user, practice_session_id)
        latest = get_latest_practice_media_job(db, session_row)
        if latest is None:
            return None
        job, turn = latest
        return media_job_response(job, turn.practice_turn_id)
    except PracticeServiceError as exc:
        _raise_http(exc)


@router.get(
    "/api/practice-sessions/{practice_session_id}/messages",
    response_model=PracticeConversationPage,
)
def get_conversation_messages(
    practice_session_id: str,
    before: str | None = None,
    limit: int = Query(default=30, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticeConversationPage:
    try:
        session_row = get_owned_practice_session(db, user, practice_session_id)
        return list_practice_conversation(db, session_row, before=before, limit=limit)
    except PracticeServiceError as exc:
        _raise_http(exc)


@router.post(
    "/api/practice-sessions/{practice_session_id}/turns",
    response_model=PracticeTurnResponse,
)
def submit_turn(
    practice_session_id: str,
    body: PracticeTurnRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticeTurnResponse:
    try:
        session_row = get_owned_practice_session(db, user, practice_session_id)
        turn, _ = submit_practice_turn(
            db,
            session_row,
            request_id=body.request_id,
            turn_id=body.turn_id,
            user_answer=body.user_answer,
            timed_out=body.timed_out,
            response_time_seconds=body.response_time_seconds,
        )
        media_job = queue_practice_media_job(db, session_row, turn)
        if media_job is not None and media_job.status == "queued":
            launch_practice_media_job(media_job.media_job_id)
        return PracticeTurnResponse(
            practice_turn_id=turn.practice_turn_id,
            attempt_no=turn.attempt_no,
            evaluation=(
                PracticeTurnEvaluation.model_validate(turn.evaluation_payload)
                if turn.evaluation_payload is not None
                else None
            ),
            dialogue_response=turn.dialogue_response,
            media=(
                media_job_response(media_job, turn.practice_turn_id)
                if media_job is not None
                else None
            ),
            session=session_response(session_row),
        )
    except PracticeServiceError as exc:
        _raise_http(exc)


@router.get(
    "/api/practice-media-jobs/{media_job_id}",
    response_model=PracticeMediaJobResponse,
)
def get_media_job(
    media_job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticeMediaJobResponse:
    try:
        job, turn = get_owned_practice_media_job(db, user, media_job_id)
        return media_job_response(job, turn.practice_turn_id)
    except PracticeServiceError as exc:
        _raise_http(exc)


@router.get("/api/practice-media-jobs/{media_job_id}/audio")
def get_media_audio(
    media_job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        job, _turn = get_owned_practice_media_job(db, user, media_job_id)
        if not job.audio_relpath:
            raise PracticeServiceError(
                "practice_media_audio_not_ready",
                "연습 아바타 음성이 아직 준비되지 않았습니다.",
                409,
            )
        path = resolve_media_file(job.audio_relpath)
        if not path.is_file():
            raise PracticeServiceError(
                "practice_media_audio_missing",
                "생성된 연습 아바타 음성 파일을 찾을 수 없습니다.",
                404,
            )
        return FileResponse(path, media_type="audio/wav", filename="speech.wav")
    except PracticeServiceError as exc:
        _raise_http(exc)


@router.get("/api/practice-media-jobs/{media_job_id}/video")
def get_media_video(
    media_job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        job, _turn = get_owned_practice_media_job(db, user, media_job_id)
        if job.status != "completed" or not job.video_relpath:
            raise PracticeServiceError(
                "practice_media_not_ready",
                "연습 아바타 영상이 아직 준비되지 않았습니다.",
                409,
            )
        path = resolve_media_file(job.video_relpath)
        if not path.is_file():
            raise PracticeServiceError(
                "practice_media_file_missing",
                "완료된 연습 아바타 영상 파일을 찾을 수 없습니다.",
                404,
            )
        return FileResponse(path, media_type="video/mp4", filename="speaking.mp4")
    except PracticeServiceError as exc:
        _raise_http(exc)


@router.post(
    "/api/practice-sessions/{practice_session_id}/advance",
    response_model=PracticeTurnResponse,
)
def advance_dialogue(
    practice_session_id: str,
    body: PracticeAdvanceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticeTurnResponse:
    try:
        session_row = get_owned_practice_session(db, user, practice_session_id)
        turn = advance_practice_dialogue(
            db,
            session_row,
            request_id=body.request_id,
            turn_id=body.turn_id,
            destination=body.destination,
        )
        return PracticeTurnResponse(
            practice_turn_id=turn.practice_turn_id,
            attempt_no=turn.attempt_no,
            evaluation=None,
            dialogue_response=None,
            session=session_response(session_row),
        )
    except PracticeServiceError as exc:
        _raise_http(exc)


@router.post(
    "/api/practice-sessions/{practice_session_id}/final-action",
    response_model=PracticeTurnResponse,
)
def submit_final_action(
    practice_session_id: str,
    body: PracticeFinalActionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticeTurnResponse:
    try:
        session_row = get_owned_practice_session(db, user, practice_session_id)
        turn, _, _ = submit_practice_final_action(
            db,
            session_row,
            request_id=body.request_id,
            selected_action=body.selected_action,
            response_time_seconds=body.response_time_seconds,
        )
        return PracticeTurnResponse(
            practice_turn_id=turn.practice_turn_id,
            attempt_no=turn.attempt_no,
            evaluation=None,
            dialogue_response=None,
            session=session_response(session_row),
        )
    except PracticeServiceError as exc:
        _raise_http(exc)


@router.get(
    "/api/practice-sessions/{practice_session_id}/result",
    response_model=PracticeResultResponse,
)
def get_result(
    practice_session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticeResultResponse:
    try:
        session_row = get_owned_practice_session(db, user, practice_session_id)
        if session_row.result is None:
            raise PracticeServiceError("practice_result_not_ready", "아직 연습 결과가 생성되지 않았습니다.", 409)
        return PracticeResultResponse(result=PracticeResult.model_validate(session_row.result))
    except PracticeServiceError as exc:
        _raise_http(exc)
