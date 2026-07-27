"""Practice-turn media job orchestration.

The request path only creates and reads jobs. Heavy Supertonic/MuseTalk work is
performed by ``app.workers.practice_media`` with its own database session.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.practice import PracticeMediaJob, PracticeSession, PracticeTurn
from app.models.user import User
from app.schemas.practice import PracticeMediaJobResponse
from app.services.practice import PracticeServiceError, load_approved_practice_assets


_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def practice_media_enabled() -> bool:
    return os.getenv("PRACTICE_MEDIA_ENABLED", "false").lower() == "true"


def practice_media_video_enabled() -> bool:
    """TTS만 남기고 립싱크 영상 생성을 끌 수 있게 한다 (저사양 GPU 실검증용)."""

    return os.getenv("PRACTICE_MEDIA_VIDEO_ENABLED", "true").lower() == "true"


def practice_media_root() -> Path:
    configured = os.getenv("PRACTICE_MEDIA_ROOT")
    return (
        Path(configured).expanduser().resolve()
        if configured
        else (_BACKEND_ROOT / "var" / "practice-media").resolve()
    )


def _speech_source(session_row: PracticeSession, turn: PracticeTurn) -> str:
    """Speak the reaction to the submitted answer; fall back to the scene prompt.

    장면 질문은 이미 한 번 발화됐으므로 반응에 이어 붙이지 않는다. 화면·대화 기록에
    남는 중개사 대사는 실제로 발화한 내용과 같아야 한다.
    """

    if turn.dialogue_response:
        return turn.dialogue_response.strip()
    scenario, _ = load_approved_practice_assets(session_row.scenario_id)
    current_prompt = next(
        (
            item.prompt
            for item in scenario.dialogue_turns
            if item.turn_id == session_row.current_state
        ),
        None,
    )
    return (current_prompt or "").strip()


def avatar_speech_text(dialogue_response: str) -> str:
    """Keep generated video short while the UI retains the full dialogue text."""

    text = " ".join(dialogue_response.split())
    max_sentences = max(
        1,
        int(os.getenv("PRACTICE_MEDIA_MAX_SPEECH_SENTENCES", "2")),
    )
    max_chars = max(
        20,
        int(os.getenv("PRACTICE_MEDIA_MAX_SPEECH_CHARS", "65")),
    )
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?。！？])\s+", text)
        if sentence.strip()
    ]
    selected = " ".join(sentences[:max_sentences]) if sentences else text
    if len(selected) <= max_chars:
        return selected
    clipped = selected[: max_chars + 1].rsplit(" ", 1)[0].strip()
    if len(clipped) < max_chars // 2:
        clipped = selected[:max_chars].strip()
    return clipped.rstrip(" ,;:") + "."


def queue_initial_practice_media_job(
    db: Session,
    session_row: PracticeSession,
) -> PracticeMediaJob | None:
    """Queue the first counterparty prompt without creating an evaluation turn."""

    if not practice_media_enabled():
        return None

    request_id = f"initial-media-{session_row.practice_session_id}"
    anchor = db.scalar(
        select(PracticeTurn).where(
            PracticeTurn.practice_session_fk == session_row.id,
            PracticeTurn.request_id == request_id,
        )
    )
    if anchor is None:
        scenario, _ = load_approved_practice_assets(session_row.scenario_id)
        prompt = next(
            (
                item.prompt
                for item in scenario.dialogue_turns
                if item.turn_id == session_row.current_state
            ),
            None,
        )
        if not prompt:
            return None
        anchor = PracticeTurn(
            practice_turn_id=uuid.uuid4().hex,
            practice_session_fk=session_row.id,
            turn_id="MEDIA-INTRO",
            attempt_no=0,
            request_id=request_id,
            input_payload={"kind": "initial_prompt"},
            evaluation_payload=None,
            dialogue_generation_payload={"source": "scenario_initial_prompt"},
            dialogue_response=prompt,
        )
        db.add(anchor)
        db.commit()
        db.refresh(anchor)

    return queue_practice_media_job(db, session_row, anchor)


def queue_practice_media_job(
    db: Session,
    session_row: PracticeSession,
    turn: PracticeTurn,
) -> PracticeMediaJob | None:
    if not practice_media_enabled() or not (turn.dialogue_response or "").strip():
        return None

    existing = db.scalar(
        select(PracticeMediaJob).where(PracticeMediaJob.practice_turn_fk == turn.id)
    )
    if existing is not None:
        return existing

    full_speech = _speech_source(session_row, turn)
    if not full_speech:
        return None
    speech_text = avatar_speech_text(full_speech)
    job = PracticeMediaJob(
        media_job_id=uuid.uuid4().hex,
        practice_session_fk=session_row.id,
        practice_turn_fk=turn.id,
        status="queued",
        speech_text=speech_text,
        provider="supertonic-3+musetalk-1.5",
        settings_payload={
            "tts_voice": os.getenv("SUPERTONIC_VOICE", "F1"),
            "tts_language": os.getenv("SUPERTONIC_LANGUAGE", "ko"),
            "tts_steps": int(os.getenv("SUPERTONIC_TOTAL_STEPS", "8")),
            "tts_speed": float(os.getenv("SUPERTONIC_SPEED", "1.1")),
            "musetalk_version": os.getenv("MUSETALK_VERSION", "v15"),
            "musetalk_batch_size": int(os.getenv("MUSETALK_BATCH_SIZE", "12")),
            "musetalk_extra_margin": int(
                os.getenv("MUSETALK_EXTRA_MARGIN", "8")
            ),
            "musetalk_parsing_mode": os.getenv("MUSETALK_PARSING_MODE", "jaw"),
            "musetalk_left_cheek_width": int(
                os.getenv("MUSETALK_LEFT_CHEEK_WIDTH", "80")
            ),
            "musetalk_right_cheek_width": int(
                os.getenv("MUSETALK_RIGHT_CHEEK_WIDTH", "80")
            ),
            "speech_truncated": speech_text != full_speech,
            "source_character_count": len(full_speech),
            "speech_character_count": len(speech_text),
            "max_audio_seconds": float(
                os.getenv("PRACTICE_MEDIA_MAX_AUDIO_SECONDS", "9")
            ),
            "target_total_seconds": float(
                os.getenv("PRACTICE_MEDIA_TARGET_SECONDS", "16")
            ),
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_owned_practice_media_job(
    db: Session,
    user: User,
    media_job_id: str,
) -> tuple[PracticeMediaJob, PracticeTurn]:
    row = db.execute(
        select(PracticeMediaJob, PracticeTurn)
        .join(
            PracticeSession,
            PracticeSession.id == PracticeMediaJob.practice_session_fk,
        )
        .join(PracticeTurn, PracticeTurn.id == PracticeMediaJob.practice_turn_fk)
        .where(
            PracticeMediaJob.media_job_id == media_job_id,
            PracticeSession.user_id == user.id,
        )
    ).one_or_none()
    if row is None:
        raise PracticeServiceError(
            "practice_media_job_not_found",
            "연습 아바타 미디어 작업을 찾을 수 없습니다.",
            404,
        )
    return row[0], row[1]


def get_latest_practice_media_job(
    db: Session,
    session_row: PracticeSession,
) -> tuple[PracticeMediaJob, PracticeTurn] | None:
    row = db.execute(
        select(PracticeMediaJob, PracticeTurn)
        .join(PracticeTurn, PracticeTurn.id == PracticeMediaJob.practice_turn_fk)
        .where(PracticeMediaJob.practice_session_fk == session_row.id)
        .order_by(PracticeMediaJob.id.desc())
        .limit(1)
    ).one_or_none()
    return (row[0], row[1]) if row is not None else None


def media_job_response(
    job: PracticeMediaJob,
    turn: PracticeTurn,
) -> PracticeMediaJobResponse:
    return PracticeMediaJobResponse(
        media_job_id=job.media_job_id,
        practice_turn_id=turn.practice_turn_id,
        media_kind=(
            "initial_prompt"
            if turn.input_payload.get("kind") == "initial_prompt"
            else "dialogue_response"
        ),
        status=job.status,
        provider=job.provider,
        speech_text=job.speech_text,
        audio_url=(
            f"/api/practice-media-jobs/{job.media_job_id}/audio"
            if job.audio_relpath
            else None
        ),
        video_url=(
            f"/api/practice-media-jobs/{job.media_job_id}/video"
            if job.status == "completed" and job.video_relpath
            else None
        ),
        error_code=job.error_code,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def resolve_media_file(relpath: str) -> Path:
    root = practice_media_root()
    resolved = (root / relpath).resolve()
    if not resolved.is_relative_to(root):
        raise PracticeServiceError(
            "practice_media_file_invalid",
            "연습 아바타 미디어 경로가 올바르지 않습니다.",
            500,
        )
    return resolved
