from pathlib import Path
from types import SimpleNamespace

from app.workers import practice_media


def test_generate_video_supports_separate_source_and_asset_roots(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    asset_root = tmp_path / "assets"
    inference_script = source_root / "scripts" / "inference.py"
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

    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        result_dir = Path(command[command.index("--result_dir") + 1])
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / "generated.mp4").write_bytes(b"video")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(practice_media.subprocess, "run", fake_run)

    output = practice_media._generate_video(audio, job_dir)

    assert output.name == "generated.mp4"
    assert captured["cwd"] == asset_root
    assert captured["env"]["PYTHONPATH"] == str(source_root)
    assert captured["command"][:2] == ["musetalk-python", str(inference_script)]
