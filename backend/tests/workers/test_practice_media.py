from pathlib import Path
from types import SimpleNamespace

from app.services import practice_media as practice_media_service
from app.services.practice_media import avatar_speech_text
from app.workers import practice_media


def test_initial_prompt_media_uses_a_non_evaluation_anchor(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PRACTICE_MEDIA_ENABLED", "true")
    prompt = "첫 계약 질문입니다. 이 조건으로 진행해도 괜찮으시죠?"
    monkeypatch.setattr(
        practice_media_service,
        "load_approved_practice_assets",
        lambda _scenario_id: (
            SimpleNamespace(
                dialogue_turns=[
                    SimpleNamespace(turn_id="TURN-01", prompt=prompt),
                ]
            ),
            None,
        ),
    )
    captured: dict[str, object] = {}

    class FakeDb:
        def scalar(self, _query):
            return None

        def add(self, row):
            captured["anchor"] = row

        def commit(self):
            return None

        def refresh(self, _row):
            return None

    expected_job = object()

    def fake_queue(_db, _session, turn):
        captured["queued_turn"] = turn
        return expected_job

    monkeypatch.setattr(
        practice_media_service,
        "queue_practice_media_job",
        fake_queue,
    )
    session = SimpleNamespace(
        id=7,
        practice_session_id="session-001",
        scenario_id="scenario-001",
        current_state="TURN-01",
    )

    result = practice_media_service.queue_initial_practice_media_job(FakeDb(), session)

    anchor = captured["anchor"]
    assert result is expected_job
    assert captured["queued_turn"] is anchor
    assert anchor.turn_id == "MEDIA-INTRO"
    assert anchor.attempt_no == 0
    assert anchor.input_payload == {"kind": "initial_prompt"}
    assert anchor.evaluation_payload is None
    assert anchor.dialogue_response == prompt


def test_speech_source_speaks_only_the_reaction(monkeypatch) -> None:
    """장면 질문은 이미 발화됐으므로 반응에 덧붙이지 않는다."""

    prompt = "이 조건으로 진행해도 괜찮으시죠?"
    monkeypatch.setattr(
        practice_media_service,
        "load_approved_practice_assets",
        lambda _scenario_id: (
            SimpleNamespace(
                dialogue_turns=[SimpleNamespace(turn_id="TURN-02", prompt=prompt)]
            ),
            None,
        ),
    )
    session = SimpleNamespace(scenario_id="scenario-001", current_state="TURN-02")
    reaction = "현재 특약에는 반환 시점이 없습니다."

    assert practice_media_service._speech_source(
        session,
        SimpleNamespace(turn_id="TURN-01", dialogue_response=reaction),
    ) == reaction

    # 반응이 없을 때만 지금 장면 대사를 말한다.
    assert practice_media_service._speech_source(
        session,
        SimpleNamespace(turn_id="TURN-02", dialogue_response=None),
    ) == prompt


def test_generate_video_supports_separate_source_and_asset_roots(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    asset_root = tmp_path / "assets"
    inference_script = source_root / "scripts" / "realtime_inference.py"
    unet_model = asset_root / "models" / "musetalkV15" / "unet.pth"
    unet_config = asset_root / "models" / "musetalkV15" / "musetalk.json"
    avatar = tmp_path / "avatar.mp4"
    audio = tmp_path / "speech.wav"
    job_dir = tmp_path / "job"

    for path in (inference_script, unet_model, unet_config, avatar, audio):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")
    job_dir.mkdir()

    monkeypatch.setenv("MUSETALK_ROOT", str(source_root))
    monkeypatch.setenv("MUSETALK_ASSET_ROOT", str(asset_root))
    monkeypatch.setenv("MUSETALK_SOURCE_AVATAR", str(avatar))
    monkeypatch.setenv("MUSETALK_UNET_MODEL_PATH", str(unet_model))
    monkeypatch.setenv("MUSETALK_UNET_CONFIG", str(unet_config))
    monkeypatch.setenv("MUSETALK_PYTHON", "musetalk-python")
    monkeypatch.setenv("MUSETALK_EXTRA_MARGIN", "8")
    monkeypatch.setenv("MUSETALK_PARSING_MODE", "jaw")
    monkeypatch.setenv("MUSETALK_LEFT_CHEEK_WIDTH", "80")
    monkeypatch.setenv("MUSETALK_RIGHT_CHEEK_WIDTH", "80")
    monkeypatch.delenv("PYTHONPATH", raising=False)

    captured: dict[str, Path] = {}

    class FakePersistentClient:
        def generate(self, audio_path: Path, output_path: Path) -> dict[str, object]:
            captured["audio_path"] = audio_path
            captured["output_path"] = output_path
            output_path.write_bytes(b"video")
            return {"total_ms": 1, "frames": 1, "effective_fps": 1000}

    client = practice_media._PersistentMuseTalkClient()
    settings = client._settings()
    ready_path = tmp_path / "ready.json"
    command = client._command(settings, ready_path)
    monkeypatch.setattr(
        practice_media,
        "_persistent_musetalk_client",
        lambda: FakePersistentClient(),
    )

    output, metrics = practice_media._generate_video(audio, job_dir)

    assert output == job_dir / "speaking.mp4"
    assert metrics["effective_fps"] == 1000
    assert captured == {"audio_path": audio, "output_path": output}
    assert settings["root"] == source_root
    assert settings["asset_root"] == asset_root
    assert command[:2] == [
        "musetalk-python",
        str(practice_media._RUNTIME_SCRIPT),
    ]
    assert command[command.index("--musetalk-root") + 1] == str(source_root)
    assert command[command.index("--asset-root") + 1] == str(asset_root)
    assert command[command.index("--extra-margin") + 1] == "8"
    assert command[command.index("--parsing-mode") + 1] == "jaw"
    assert command[command.index("--left-cheek-width") + 1] == "80"
    assert command[command.index("--right-cheek-width") + 1] == "80"


def _run_job_with_fakes(monkeypatch, tmp_path: Path, video: object) -> SimpleNamespace:
    """음성 생성만 대체하고 한 건의 미디어 작업을 실제 흐름대로 실행한다."""

    job = SimpleNamespace(
        media_job_id="job-1",
        status="queued",
        speech_text="안녕하세요.",
        settings_payload={"target_total_seconds": 15},
        started_at=None,
        audio_relpath=None,
        video_relpath=None,
        error_code=None,
        completed_at=None,
    )

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def scalar(self, _query):
            return job

        def commit(self):
            return None

    monkeypatch.setattr(practice_media, "SessionLocal", FakeSession)
    monkeypatch.setattr(practice_media, "practice_media_root", lambda: tmp_path)
    monkeypatch.setattr(
        practice_media,
        "_generate_audio",
        lambda _text, _settings, path: path.write_bytes(b"wav"),
    )
    monkeypatch.setattr(practice_media, "_generate_video", video)

    practice_media._run_locked_practice_media_job("job-1")
    return job


def test_video_disabled_job_completes_with_audio_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PRACTICE_MEDIA_VIDEO_ENABLED", "false")

    def fail_video(*_args, **_kwargs):
        raise AssertionError("영상 생성이 꺼졌는데 MuseTalk이 호출됐다")

    job = _run_job_with_fakes(monkeypatch, tmp_path, fail_video)

    assert job.status == "completed"
    assert job.audio_relpath == str(Path("job-1") / "speech.wav")
    assert job.video_relpath is None
    assert job.settings_payload["video_disabled"] is True


def test_video_enabled_job_still_runs_musetalk(monkeypatch, tmp_path: Path) -> None:
    """기본값(영상 켜짐)에서는 립싱크 생성 경로가 그대로 동작한다."""

    monkeypatch.delenv("PRACTICE_MEDIA_VIDEO_ENABLED", raising=False)
    calls: list[Path] = []

    def fake_video(audio_path: Path, job_dir: Path):
        calls.append(audio_path)
        output = job_dir / "speaking.mp4"
        output.write_bytes(b"video")
        return output, {"total_ms": 1, "frames": 25, "effective_fps": 25}

    job = _run_job_with_fakes(monkeypatch, tmp_path, fake_video)

    assert calls == [tmp_path / "job-1" / "speech.wav"]
    assert job.status == "completed"
    assert job.video_relpath == str(Path("job-1") / "speaking.mp4")
    assert job.audio_relpath == str(Path("job-1") / "speech.wav")
    assert "video_disabled" not in job.settings_payload
    assert job.settings_payload["timings_ms"]["video"] == 1


def test_avatar_speech_text_keeps_full_first_sentence(monkeypatch) -> None:
    monkeypatch.setenv("PRACTICE_MEDIA_MAX_SPEECH_SENTENCES", "1")
    monkeypatch.setenv("PRACTICE_MEDIA_MAX_SPEECH_CHARS", "48")

    assert avatar_speech_text("첫 문장입니다. 두 번째 문장은 화면에만 표시합니다.") == "첫 문장입니다."


def test_avatar_speech_text_keeps_two_sentences_up_to_65_chars(monkeypatch) -> None:
    monkeypatch.setenv("PRACTICE_MEDIA_MAX_SPEECH_SENTENCES", "2")
    monkeypatch.setenv("PRACTICE_MEDIA_MAX_SPEECH_CHARS", "65")
    prompt = (
        "임대인분은 특약대로 다음 세입자가 들어오면 보증금을 바로 반환하겠다고 하십니다. "
        "이 조건으로 진행해도 괜찮으시죠?"
    )

    assert len(prompt) == 63
    assert avatar_speech_text(prompt) == prompt


def test_avatar_speech_text_caps_long_dialogue(monkeypatch) -> None:
    monkeypatch.setenv("PRACTICE_MEDIA_MAX_SPEECH_SENTENCES", "1")
    monkeypatch.setenv("PRACTICE_MEDIA_MAX_SPEECH_CHARS", "20")

    result = avatar_speech_text("계약 조건을 확인하기 전에는 송금하지 말고 관련 서류를 먼저 요청하세요.")

    assert result.endswith(".")
    assert len(result) <= 21
