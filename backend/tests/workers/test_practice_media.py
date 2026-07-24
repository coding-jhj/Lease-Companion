from pathlib import Path

from app.services.practice_media import avatar_speech_text
from app.workers import practice_media


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


def test_avatar_speech_text_keeps_full_first_sentence(monkeypatch) -> None:
    monkeypatch.setenv("PRACTICE_MEDIA_MAX_SPEECH_SENTENCES", "1")
    monkeypatch.setenv("PRACTICE_MEDIA_MAX_SPEECH_CHARS", "48")

    assert avatar_speech_text("첫 문장입니다. 두 번째 문장은 화면에만 표시합니다.") == "첫 문장입니다."


def test_avatar_speech_text_caps_long_dialogue(monkeypatch) -> None:
    monkeypatch.setenv("PRACTICE_MEDIA_MAX_SPEECH_SENTENCES", "1")
    monkeypatch.setenv("PRACTICE_MEDIA_MAX_SPEECH_CHARS", "20")

    result = avatar_speech_text("계약 조건을 확인하기 전에는 송금하지 말고 관련 서류를 먼저 요청하세요.")

    assert result.endswith(".")
    assert len(result) <= 21
