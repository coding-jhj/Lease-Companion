"""Generate Supertonic 3 audio and a MuseTalk speaking clip for one job."""

from __future__ import annotations

import atexit
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import wave

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.practice import PracticeMediaJob
from app.services.practice_media import (
    practice_media_root,
    practice_media_video_enabled,
)

logger = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_RUNTIME_SCRIPT = _REPO_ROOT / "scripts" / "avatar" / "musetalk_realtime_worker.py"
_MEDIA_EXECUTOR: ThreadPoolExecutor | None = None
_MEDIA_EXECUTOR_LOCK = threading.Lock()


def _media_executor() -> ThreadPoolExecutor:
    global _MEDIA_EXECUTOR
    with _MEDIA_EXECUTOR_LOCK:
        if _MEDIA_EXECUTOR is None:
            _MEDIA_EXECUTOR = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="practice-media",
            )
        return _MEDIA_EXECUTOR


class PracticeMediaGenerationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def launch_practice_media_job(media_job_id: str) -> None:
    """Queue work without creating a new Python/MuseTalk process per turn."""

    if "PYTEST_CURRENT_TEST" in os.environ:
        return
    try:
        _media_executor().submit(run_practice_media_job, media_job_id)
    except RuntimeError:
        logger.exception("Could not launch practice media worker for job %s", media_job_id)
        _mark_failed(media_job_id, "practice_media_worker_launch_failed")


def warm_practice_media_worker() -> None:
    """Warm the persistent GPU runtime in the background during API startup."""

    if (
        os.getenv("PRACTICE_MEDIA_ENABLED", "false").lower() != "true"
        or os.getenv("PRACTICE_MEDIA_WARM_ON_STARTUP", "true").lower() != "true"
        or "PYTEST_CURRENT_TEST" in os.environ
    ):
        return
    try:
        _media_executor().submit(_warm_practice_media_runtime)
    except RuntimeError:
        logger.exception("Could not schedule MuseTalk runtime warm-up")


def _warm_practice_media_runtime() -> None:
    runtime_dir = practice_media_root() / ".musetalk-runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    audio_path = runtime_dir / "supertonic-warmup.wav"
    try:
        _generate_audio(
            "확인해 보겠습니다.",
            {
                "tts_voice": os.getenv("SUPERTONIC_VOICE", "F1"),
                "tts_language": os.getenv("SUPERTONIC_LANGUAGE", "ko"),
                "tts_steps": int(os.getenv("SUPERTONIC_TOTAL_STEPS", "8")),
                "tts_speed": float(os.getenv("SUPERTONIC_SPEED", "1.1")),
            },
            audio_path,
        )
        if practice_media_video_enabled():
            _persistent_musetalk_client().ensure_started()
    except Exception:
        logger.exception("Practice media runtime warm-up failed")
    finally:
        audio_path.unlink(missing_ok=True)


def shutdown_practice_media_worker() -> None:
    """Stop accepting work and terminate the dedicated MuseTalk runtime."""

    global _MEDIA_EXECUTOR
    with _MEDIA_EXECUTOR_LOCK:
        executor = _MEDIA_EXECUTOR
        _MEDIA_EXECUTOR = None
    if executor is not None:
        executor.shutdown(wait=True, cancel_futures=True)
    _persistent_musetalk_client().close()


class _PersistentMuseTalkClient:
    """Own one long-lived process in the dedicated MuseTalk Python environment."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._log_handle = None
        self._ready_path: Path | None = None

    def _settings(self) -> dict[str, object]:
        musetalk_root = _required_path("MUSETALK_ROOT")
        asset_root = (
            _required_path("MUSETALK_ASSET_ROOT")
            if os.getenv("MUSETALK_ASSET_ROOT")
            else musetalk_root
        )
        source_avatar = Path(
            os.getenv(
                "MUSETALK_SOURCE_AVATAR",
                str(
                    _REPO_ROOT
                    / "frontend"
                    / "public"
                    / "practice"
                    / "avatar"
                    / "musetalk-source.mp4"
                ),
            )
        ).expanduser().resolve()
        if not source_avatar.is_file():
            raise PracticeMediaGenerationError(
                "musetalk_source_avatar_not_found",
                "The configured MuseTalk source avatar does not exist.",
            )
        if not (musetalk_root / "scripts" / "realtime_inference.py").is_file():
            raise PracticeMediaGenerationError(
                "musetalk_source_not_found",
                "MuseTalk scripts/realtime_inference.py was not found.",
            )
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
                "MuseTalk model files are not configured.",
            )
        if not _RUNTIME_SCRIPT.is_file():
            raise PracticeMediaGenerationError(
                "musetalk_runtime_not_found",
                "The persistent MuseTalk runtime script was not found.",
            )
        return {
            "python": os.getenv("MUSETALK_PYTHON", "python"),
            "root": musetalk_root,
            "asset_root": asset_root,
            "source_avatar": source_avatar,
            "version": version,
            "unet_model_path": unet_model_path,
            "unet_config": unet_config,
        }

    def _command(self, settings: dict[str, object], ready_path: Path) -> list[str]:
        command = [
            str(settings["python"]),
            str(_RUNTIME_SCRIPT),
            "--musetalk-root",
            str(settings["root"]),
            "--asset-root",
            str(settings["asset_root"]),
            "--source-avatar",
            str(settings["source_avatar"]),
            "--unet-model-path",
            str(settings["unet_model_path"]),
            "--unet-config",
            str(settings["unet_config"]),
            "--version",
            str(settings["version"]),
            "--batch-size",
            os.getenv("MUSETALK_BATCH_SIZE", "12"),
            "--fps",
            os.getenv("MUSETALK_FPS", "25"),
            "--avatar-seconds",
            os.getenv("MUSETALK_AVATAR_SECONDS", "4"),
            "--bbox-shift",
            os.getenv("MUSETALK_BBOX_SHIFT", "0"),
            "--extra-margin",
            os.getenv("MUSETALK_EXTRA_MARGIN", "8"),
            "--parsing-mode",
            os.getenv("MUSETALK_PARSING_MODE", "jaw"),
            "--left-cheek-width",
            os.getenv("MUSETALK_LEFT_CHEEK_WIDTH", "80"),
            "--right-cheek-width",
            os.getenv("MUSETALK_RIGHT_CHEEK_WIDTH", "80"),
            "--video-encoder",
            os.getenv("MUSETALK_VIDEO_ENCODER", "h264_nvenc"),
            "--ready-path",
            str(ready_path),
        ]
        if os.getenv("MUSETALK_USE_FLOAT16", "true").lower() == "true":
            command.append("--use-float16")
        return command

    def ensure_started(self) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return
            try:
                self._start_locked()
            except Exception:
                self._terminate_locked()
                raise

    def _start_locked(self) -> None:
        settings = self._settings()
        runtime_dir = practice_media_root() / ".musetalk-runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        ready_path = runtime_dir / "ready.json"
        ready_path.unlink(missing_ok=True)
        log_path = runtime_dir / "runtime.log"
        self._log_handle = log_path.open("a", encoding="utf-8")
        process_env = os.environ.copy()
        process_env["PYTHONPATH"] = str(settings["root"])
        kwargs: dict[str, object] = {
            "cwd": str(settings["asset_root"]),
            "env": process_env,
            "stdin": subprocess.PIPE,
            "stdout": self._log_handle,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "bufsize": 1,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._process = subprocess.Popen(
            self._command(settings, ready_path),
            **kwargs,
        )
        self._ready_path = ready_path
        deadline = time.monotonic() + int(
            os.getenv("PRACTICE_MEDIA_WARMUP_TIMEOUT_SECONDS", "600")
        )
        while time.monotonic() < deadline:
            if ready_path.is_file():
                payload = json.loads(ready_path.read_text(encoding="utf-8"))
                if payload.get("status") == "ready":
                    logger.info(
                        "MuseTalk runtime ready in %sms; warmup=%sms encoder=%s cache=%s",
                        payload.get("startup_ms"),
                        payload.get("warmup_ms"),
                        payload.get("video_encoder"),
                        payload.get("avatar_cache"),
                    )
                    return
                raise PracticeMediaGenerationError(
                    "musetalk_runtime_start_failed",
                    str(payload.get("error") or "MuseTalk runtime failed to start."),
                )
            if self._process.poll() is not None:
                raise PracticeMediaGenerationError(
                    "musetalk_runtime_start_failed",
                    f"MuseTalk runtime exited with code {self._process.returncode}.",
                )
            time.sleep(0.25)
        self._terminate_locked()
        raise PracticeMediaGenerationError(
            "musetalk_runtime_start_timeout",
            "MuseTalk runtime warm-up timed out.",
        )

    def generate(self, audio_path: Path, output_path: Path) -> dict[str, object]:
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                self._start_locked()
            assert self._process is not None
            assert self._process.stdin is not None
            result_path = output_path.with_suffix(".result.json")
            result_path.unlink(missing_ok=True)
            request = {
                "command": "generate",
                "audio_path": str(audio_path.resolve()),
                "output_path": str(output_path.resolve()),
                "result_path": str(result_path.resolve()),
            }
            self._process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            self._process.stdin.flush()
            deadline = time.monotonic() + int(
                os.getenv("PRACTICE_MEDIA_TIMEOUT_SECONDS", "600")
            )
            while time.monotonic() < deadline:
                if result_path.is_file():
                    payload = json.loads(result_path.read_text(encoding="utf-8"))
                    result_path.unlink(missing_ok=True)
                    if payload.get("status") == "completed" and output_path.is_file():
                        return payload
                    raise PracticeMediaGenerationError(
                        str(payload.get("error_code") or "musetalk_generation_failed"),
                        str(payload.get("message") or "MuseTalk failed to generate video."),
                    )
                if self._process.poll() is not None:
                    raise PracticeMediaGenerationError(
                        "musetalk_runtime_exited",
                        f"MuseTalk runtime exited with code {self._process.returncode}.",
                    )
                time.sleep(0.1)
            raise PracticeMediaGenerationError(
                "musetalk_timeout",
                "MuseTalk generation timed out.",
            )

    def _terminate_locked(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None

    def close(self) -> None:
        with self._lock:
            if (
                self._process is not None
                and self._process.poll() is None
                and self._process.stdin is not None
            ):
                try:
                    self._process.stdin.write('{"command":"shutdown"}\n')
                    self._process.stdin.flush()
                    self._process.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            self._terminate_locked()


@lru_cache(maxsize=1)
def _persistent_musetalk_client() -> _PersistentMuseTalkClient:
    return _PersistentMuseTalkClient()


atexit.register(shutdown_practice_media_worker)


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
        _cap_audio_duration(output_path)
    except PracticeMediaGenerationError:
        raise
    except Exception as exc:
        raise PracticeMediaGenerationError(
            "supertonic_generation_failed",
            "Supertonic failed to generate audio.",
        ) from exc


def _cap_audio_duration(output_path: Path) -> None:
    max_seconds = float(os.getenv("PRACTICE_MEDIA_MAX_AUDIO_SECONDS", "9"))
    with wave.open(str(output_path), "rb") as audio:
        duration = audio.getnframes() / audio.getframerate()
    if duration <= max_seconds:
        return
    speed_ratio = duration / max_seconds
    if speed_ratio > 2:
        raise PracticeMediaGenerationError(
            "practice_media_speech_too_long",
            "Avatar speech exceeds the supported duration.",
        )
    temporary = output_path.with_name(output_path.stem + "-capped.wav")
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(output_path),
            "-filter:a",
            f"atempo={speed_ratio:.6f}",
            str(temporary),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not temporary.is_file():
        temporary.unlink(missing_ok=True)
        raise PracticeMediaGenerationError(
            "practice_media_audio_duration_cap_failed",
            "Could not fit avatar speech within the generation budget.",
        )
    temporary.replace(output_path)


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


def _generate_video(
    audio_path: Path,
    job_dir: Path,
) -> tuple[Path, dict[str, object]]:
    output_path = job_dir / "speaking.mp4"
    metrics = _persistent_musetalk_client().generate(audio_path, output_path)
    logger.info(
        "MuseTalk warm generation completed total_ms=%s frames=%s fps=%s",
        metrics.get("total_ms"),
        metrics.get("frames"),
        metrics.get("effective_fps"),
    )
    return output_path, metrics


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
        job_started = time.perf_counter()
        root = practice_media_root()
        job_dir = root / media_job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        audio_path = job_dir / "speech.wav"
        audio_started = time.perf_counter()
        _generate_audio(speech_text, settings, audio_path)
        tts_ms = round((time.perf_counter() - audio_started) * 1_000)

        with SessionLocal() as db:
            current = db.scalar(
                select(PracticeMediaJob).where(PracticeMediaJob.media_job_id == media_job_id)
            )
            if current is None:
                return
            current.audio_relpath = str(audio_path.relative_to(root))
            # ponytail: 영상 비활성이면 음성만 완료로 남긴다. video_relpath 없음 → Frontend는 음성만 재생.
            video_on = practice_media_video_enabled()
            current.status = "generating_video" if video_on else "completed"
            if not video_on:
                current.completed_at = datetime.now(timezone.utc)
                current.error_code = None
                current.settings_payload = {
                    **dict(current.settings_payload),
                    "video_disabled": True,
                    "timings_ms": {"tts": tts_ms, "end_to_end": tts_ms},
                }
            db.commit()
        if not video_on:
            logger.info(
                "연습 미디어 완료(음성만) job=%s tts_ms=%s video=disabled",
                media_job_id,
                tts_ms,
            )
            return

        generated_video, generation_metrics = _generate_video(audio_path, job_dir)
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
            total_ms = round((time.perf_counter() - job_started) * 1_000)
            target_ms = float(
                current.settings_payload.get("target_total_seconds", 15)
            ) * 1_000
            current.settings_payload = {
                **dict(current.settings_payload),
                "timings_ms": {
                    "tts": tts_ms,
                    "video": generation_metrics.get("total_ms"),
                    "audio_features": generation_metrics.get("audio_feature_ms"),
                    "inference_and_encode": generation_metrics.get(
                        "inference_and_encode_ms"
                    ),
                    "end_to_end": total_ms,
                },
                "generated_frames": generation_metrics.get("frames"),
                "effective_fps": generation_metrics.get("effective_fps"),
                "video_encoder": generation_metrics.get("video_encoder"),
                "target_met": total_ms <= target_ms,
            }
            db.commit()
        # 디버깅 데모 영상에서 육안 확인용. 값만 남기고 답변 텍스트는 찍지 않는다.
        logger.info(
            "연습 미디어 완료 job=%s tts_ms=%s video_ms=%s frames=%s fps=%s "
            "encoder=%s end_to_end_ms=%s target_met=%s",
            media_job_id,
            tts_ms,
            generation_metrics.get("total_ms"),
            generation_metrics.get("frames"),
            generation_metrics.get("effective_fps"),
            generation_metrics.get("video_encoder"),
            total_ms,
            total_ms <= target_ms,
        )
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
