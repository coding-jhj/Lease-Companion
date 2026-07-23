"""Practice-turn media job orchestration.

The request path only creates and reads jobs. Heavy Supertonic/MuseTalk work is
performed by ``app.workers.practice_media`` with its own database session.
"""

from __future__ import annotations

import os
from pathlib import Path
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.practice import PracticeMediaJob, PracticeSession, PracticeTurn
from app.models.user import User
from app.schemas.practice import PracticeMediaJobResponse
from app.services.practice import PracticeServiceError


_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def practice_media_enabled() -> bool:
    return os.getenv("PRACTICE_MEDIA_ENABLED", "false").lower() == "true"


def practice_media_root() -> Path:
    configured = os.getenv("PRACTICE_MEDIA_ROOT")
    return (
        Path(configured).expanduser().resolve()
        if configured
        else (_BACKEND_ROOT / "var" / "practice-media").resolve()
    )


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

    job = PracticeMediaJob(
        media_job_id=uuid.uuid4().hex,
        practice_session_fk=session_row.id,
        practice_turn_fk=turn.id,
        status="queued",
        speech_text=turn.dialogue_response.strip(),
        provider="supertonic-3+musetalk-1.5",
        settings_payload={
            "tts_voice": os.getenv("SUPERTONIC_VOICE", "F1"),
            "tts_language": os.getenv("SUPERTONIC_LANGUAGE", "ko"),
            "tts_steps": int(os.getenv("SUPERTONIC_TOTAL_STEPS", "8")),
            "tts_speed": float(os.getenv("SUPERTONIC_SPEED", "1.0")),
            "musetalk_version": os.getenv("MUSETALK_VERSION", "v15"),
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
    practice_turn_id: str,
) -> PracticeMediaJobResponse:
    return PracticeMediaJobResponse(
        media_job_id=job.media_job_id,
        practice_turn_id=practice_turn_id,
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
