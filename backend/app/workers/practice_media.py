"""Generate Supertonic 3 audio and a MuseTalk speaking clip for one job."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.practice import PracticeMediaJob
from app.services.practice_media import practice_media_root

logger = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_ROOT = _REPO_ROOT / "backend"


class PracticeMediaGenerationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def launch_practice_media_job(media_job_id: str) -> None:
    """Start an isolated worker so the API response never waits for TTS/video."""

    command = [sys.executable, "-m", "app.workers.practice_media", media_job_id]
    kwargs: dict = {
        "cwd": _BACKEND_ROOT,
        "env": os.environ.copy(),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(command, **kwargs)
    except OSError:
        logger.exception("Could not launch practice media worker for job %s", media_job_id)
        _mark_failed(media_job_id, "practice_media_worker_launch_failed")


@contextmanager
def _generation_lock():
    """Serialize GPU jobs across worker processes on Windows and POSIX."""

    root = practice_media_root()
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".generation.lock"
    with lock_path.open("a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"0")
            lock_file.flush()
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.25)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@lru_cache(maxsize=1)
def _supertonic():
    try:
        from supertonic import TTS
    except ImportError as exc:
        raise PracticeMediaGenerationError(
            "supertonic_not_installed",
            "Supertonic Python SDK is not installed.",
        ) from exc
    return TTS(auto_download=True)


def _generate_audio(speech_text: str, settings: dict, output_path: Path) -> None:
    try:
        tts = _supertonic()
        style = tts.get_voice_style(voice_name=settings["tts_voice"])
        wav, _duration = tts.synthesize(
            text=speech_text,
            lang=settings["tts_language"],
            voice_style=style,
            total_steps=settings["tts_steps"],
            speed=settings["tts_speed"],
        )
        tts.save_audio(wav, str(output_path))
    except PracticeMediaGenerationError:
        raise
    except Exception as exc:
        raise PracticeMediaGenerationError(
            "supertonic_generation_failed",
            "Supertonic failed to generate audio.",
        ) from exc


def _required_path(name: str) -> Path:
    value = os.getenv(name)
    if not value:
        raise PracticeMediaGenerationError(
            "musetalk_not_configured",
            f"{name} is required when practice media generation is enabled.",
        )
    path = Path(value).expanduser().resolve()
    if not path.exists():
        raise PracticeMediaGenerationError(
            "musetalk_path_not_found",
            f"{name} does not exist.",
        )
    return path


def _generate_video(audio_path: Path, job_dir: Path) -> Path:
    musetalk_root = _required_path("MUSETALK_ROOT")
    inference_script = musetalk_root / "scripts" / "inference.py"
    if not inference_script.is_file():
        raise PracticeMediaGenerationError(
            "musetalk_source_not_found",
            "MuseTalk scripts/inference.py was not found in MUSETALK_ROOT.",
        )
    asset_root = (
        _required_path("MUSETALK_ASSET_ROOT")
        if os.getenv("MUSETALK_ASSET_ROOT")
        else musetalk_root
    )
    source_avatar = Path(
        os.getenv(
            "MUSETALK_SOURCE_AVATAR",
            str(_REPO_ROOT / "frontend" / "public" / "practice" / "avatar" / "speaking.mp4"),
        )
    ).expanduser().resolve()
    if not source_avatar.is_file():
        raise PracticeMediaGenerationError(
            "musetalk_source_avatar_not_found",
            "The configured MuseTalk source avatar does not exist.",
        )

    config_path = job_dir / "musetalk-job.yaml"
    config_path.write_text(
        "task_0:\n"
        f"  video_path: {json.dumps(str(source_avatar))}\n"
        f"  audio_path: {json.dumps(str(audio_path))}\n"
        f"  bbox_shift: {int(os.getenv('MUSETALK_BBOX_SHIFT', '0'))}\n",
        encoding="utf-8",
    )
    result_dir = job_dir / "musetalk-result"
    result_dir.mkdir(parents=True, exist_ok=True)

    python_executable = os.getenv("MUSETALK_PYTHON", "python")
    version = os.getenv("MUSETALK_VERSION", "v15")
    unet_model_path = Path(
        os.getenv(
            "MUSETALK_UNET_MODEL_PATH",
            str(asset_root / "models" / "musetalkV15" / "unet.pth"),
        )
    ).expanduser().resolve()
    unet_config = Path(
        os.getenv(
            "MUSETALK_UNET_CONFIG",
            str(asset_root / "models" / "musetalkV15" / "musetalk.json"),
        )
    ).expanduser().resolve()
    if not unet_model_path.is_file() or not unet_config.is_file():
        raise PracticeMediaGenerationError(
            "musetalk_model_not_found",
            "MuseTalk 1.5 model files are not configured.",
        )

    command = [
        python_executable,
        str(inference_script),
        "--inference_config",
        str(config_path),
        "--result_dir",
        str(result_dir),
        "--unet_model_path",
        str(unet_model_path),
        "--unet_config",
        str(unet_config),
        "--version",
        version,
    ]
    ffmpeg_path = os.getenv("MUSETALK_FFMPEG_PATH")
    if ffmpeg_path:
        command.extend(["--ffmpeg_path", ffmpeg_path])
    if os.getenv("MUSETALK_USE_FLOAT16", "true").lower() == "true":
        command.append("--use_float16")
    command.extend(
        ["--batch_size", os.getenv("MUSETALK_BATCH_SIZE", "4")]
    )

    try:
        process_env = os.environ.copy()
        process_env["TEMP"] = str(job_dir)
        process_env["TMP"] = str(job_dir)
        existing_pythonpath = process_env.get("PYTHONPATH")
        process_env["PYTHONPATH"] = (
            str(musetalk_root)
            if not existing_pythonpath
            else str(musetalk_root) + os.pathsep + existing_pythonpath
        )
        completed = subprocess.run(
            command,
            cwd=asset_root,
            env=process_env,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("PRACTICE_MEDIA_TIMEOUT_SECONDS", "600")),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PracticeMediaGenerationError(
            "musetalk_timeout",
            "MuseTalk generation timed out.",
        ) from exc
    except OSError as exc:
        raise PracticeMediaGenerationError(
            "musetalk_process_failed",
            "MuseTalk process could not be started.",
        ) from exc
    if completed.returncode != 0:
        logger.warning(
            "MuseTalk failed for media job; returncode=%s stderr_tail=%s",
            completed.returncode,
            completed.stderr[-500:],
        )
        raise PracticeMediaGenerationError(
            "musetalk_generation_failed",
            "MuseTalk failed to generate video.",
        )

    outputs = sorted(result_dir.rglob("*.mp4"), key=lambda path: path.stat().st_mtime)
    if not outputs:
        raise PracticeMediaGenerationError(
            "musetalk_output_missing",
            "MuseTalk completed without an MP4 output.",
        )
    return outputs[-1]


def run_practice_media_job(media_job_id: str) -> None:
    """Run one queued media job in an isolated process."""

    with _generation_lock():
        _run_locked_practice_media_job(media_job_id)


def _run_locked_practice_media_job(media_job_id: str) -> None:

    with SessionLocal() as db:
        job = db.scalar(
            select(PracticeMediaJob).where(PracticeMediaJob.media_job_id == media_job_id)
        )
        if job is None or job.status != "queued":
            return
        speech_text = job.speech_text
        settings = dict(job.settings_payload)
        job.status = "generating_audio"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

    try:
        root = practice_media_root()
        job_dir = root / media_job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        audio_path = job_dir / "speech.wav"
        _generate_audio(speech_text, settings, audio_path)

        with SessionLocal() as db:
            current = db.scalar(
                select(PracticeMediaJob).where(PracticeMediaJob.media_job_id == media_job_id)
            )
            if current is None:
                return
            current.status = "generating_video"
            current.audio_relpath = str(audio_path.relative_to(root))
            db.commit()

        generated_video = _generate_video(audio_path, job_dir)
        final_video = job_dir / "speaking.mp4"
        if generated_video.resolve() != final_video.resolve():
            shutil.copy2(generated_video, final_video)

        with SessionLocal() as db:
            current = db.scalar(
                select(PracticeMediaJob).where(PracticeMediaJob.media_job_id == media_job_id)
            )
            if current is None:
                return
            current.status = "completed"
            current.video_relpath = str(final_video.relative_to(root))
            current.error_code = None
            current.completed_at = datetime.now(timezone.utc)
            db.commit()
    except PracticeMediaGenerationError as exc:
        logger.warning("Practice media job %s failed: %s", media_job_id, exc.code)
        _mark_failed(media_job_id, exc.code)
    except Exception:
        logger.exception("Unexpected practice media failure for job %s", media_job_id)
        _mark_failed(media_job_id, "practice_media_internal_error")


def _mark_failed(media_job_id: str, error_code: str) -> None:
    with SessionLocal() as db:
        current = db.scalar(
            select(PracticeMediaJob).where(PracticeMediaJob.media_job_id == media_job_id)
        )
        if current is None:
            return
        current.status = "failed"
        current.error_code = error_code
        current.completed_at = datetime.now(timezone.utc)
        db.commit()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m app.workers.practice_media <media_job_id>")
    run_practice_media_job(sys.argv[1])
