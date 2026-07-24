"""Persistent MuseTalk runtime used by the Lease Companion backend.

This script runs inside the dedicated MuseTalk Python environment. It keeps the
VAE, UNet, Whisper encoder and one preprocessed avatar resident between jobs.
Requests arrive as JSON lines on stdin and completion metadata is written to a
per-job JSON file so model logs never interfere with the protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from typing import Any
import wave


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-1_000:] or "Command failed.")


def _available_encoder(requested: str) -> str:
    completed = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0 and requested in completed.stdout:
        probe = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=black:s=256x256:d=0.04",
                "-frames:v",
                "1",
                "-c:v",
                requested,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            check=False,
        )
        if probe.returncode == 0:
            return requested
    return "libx264"


def _optimized_source(
    source: Path,
    cache_root: Path,
    *,
    fps: int,
    avatar_seconds: float,
) -> Path:
    signature = hashlib.sha256(
        (
            f"{source.resolve()}:{source.stat().st_size}:"
            f"{source.stat().st_mtime_ns}:{fps}:{avatar_seconds}"
        ).encode()
    ).hexdigest()[:16]
    output = cache_root / f"source-{signature}.mp4"
    if output.is_file():
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-t",
            str(avatar_seconds),
            "-vf",
            f"fps={fps}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ]
    )
    return output


def _avatar_cache_complete(path: Path) -> bool:
    return all(
        target.exists()
        for target in (
            path / "avator_info.json",
            path / "coords.pkl",
            path / "latents.pt",
            path / "mask_coords.pkl",
            path / "full_imgs",
            path / "mask",
        )
    )


class PersistentRenderer:
    def __init__(self, args: argparse.Namespace) -> None:
        startup = time.perf_counter()
        self.args = args
        self.asset_root = Path(args.asset_root).resolve()
        os.chdir(self.asset_root)
        sys.path.insert(0, str(Path(args.musetalk_root).resolve()))

        import cv2
        import numpy as np
        import torch
        from transformers import WhisperModel

        from musetalk.utils.audio_processor import AudioProcessor
        from musetalk.utils.blending import get_image_blending
        from musetalk.utils.face_parsing import FaceParsing
        from musetalk.utils.utils import datagen, load_all_model
        from scripts import realtime_inference as realtime

        self.cv2 = cv2
        self.np = np
        self.torch = torch
        self.datagen = datagen
        self.get_image_blending = get_image_blending
        self.realtime = realtime
        self.encoder = _available_encoder(args.video_encoder)

        device = torch.device(
            f"cuda:{args.gpu_id}" if torch.cuda.is_available() else "cpu"
        )
        if device.type != "cuda":
            raise RuntimeError("MuseTalk persistent runtime requires CUDA.")

        realtime.args = SimpleNamespace(
            version=args.version,
            extra_margin=args.extra_margin,
            parsing_mode=args.parsing_mode,
            left_cheek_width=args.left_cheek_width,
            right_cheek_width=args.right_cheek_width,
            audio_padding_length_left=args.audio_padding_length_left,
            audio_padding_length_right=args.audio_padding_length_right,
            skip_save_images=True,
        )
        realtime.device = device
        realtime.vae, realtime.unet, realtime.pe = load_all_model(
            unet_model_path=args.unet_model_path,
            vae_type=str(self.asset_root / "models" / "sd-vae"),
            unet_config=args.unet_config,
            device=device,
        )
        realtime.timesteps = torch.tensor([0], device=device)
        if args.use_float16:
            realtime.pe = realtime.pe.half().to(device)
            realtime.vae.vae = realtime.vae.vae.half().to(device)
            realtime.unet.model = realtime.unet.model.half().to(device)
        else:
            realtime.pe = realtime.pe.to(device)
            realtime.vae.vae = realtime.vae.vae.to(device)
            realtime.unet.model = realtime.unet.model.to(device)

        realtime.audio_processor = AudioProcessor(
            feature_extractor_path=str(self.asset_root / "models" / "whisper")
        )
        realtime.weight_dtype = realtime.unet.model.dtype
        realtime.whisper = WhisperModel.from_pretrained(
            str(self.asset_root / "models" / "whisper")
        )
        realtime.whisper = realtime.whisper.to(
            device=device,
            dtype=realtime.weight_dtype,
        ).eval()
        realtime.whisper.requires_grad_(False)
        if args.version == "v15":
            realtime.fp = FaceParsing(
                left_cheek_width=args.left_cheek_width,
                right_cheek_width=args.right_cheek_width,
            )
            bbox_shift = 0
        else:
            realtime.fp = FaceParsing()
            bbox_shift = args.bbox_shift

        cache_root = self.asset_root / "results" / "lease-companion-cache"
        source = _optimized_source(
            Path(args.source_avatar).resolve(),
            cache_root,
            fps=args.fps,
            avatar_seconds=args.avatar_seconds,
        )
        avatar_signature = hashlib.sha256(
            (
                f"{source}:{source.stat().st_mtime_ns}:{args.version}:"
                f"{bbox_shift}:{args.extra_margin}:{args.parsing_mode}"
            ).encode()
        ).hexdigest()[:16]
        avatar_id = f"lease-companion-{avatar_signature}"
        avatar_path = (
            self.asset_root / "results" / args.version / "avatars" / avatar_id
            if args.version == "v15"
            else self.asset_root / "results" / "avatars" / avatar_id
        )
        cache_ready = _avatar_cache_complete(avatar_path)
        if avatar_path.exists() and not cache_ready:
            shutil.rmtree(avatar_path)

        self.avatar = realtime.Avatar(
            avatar_id=avatar_id,
            video_path=str(source),
            bbox_shift=bbox_shift,
            batch_size=args.batch_size,
            preparation=not cache_ready,
        )
        self.device = device
        torch.cuda.synchronize(device)
        self.startup_ms = round((time.perf_counter() - startup) * 1_000)
        self.avatar_cache = "reused" if cache_ready else "created"

    def warm_up(self) -> dict[str, Any]:
        """Exercise Whisper, UNet, VAE, blending and encoder before serving."""

        runtime_dir = self.asset_root / "results" / "lease-companion-cache"
        audio_path = runtime_dir / "runtime-warmup.wav"
        with wave.open(str(audio_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16_000)
            audio.writeframes(b"\x00\x00" * 32_000)
        try:
            metrics: dict[str, Any] = {}
            total_ms = 0
            for index in range(2):
                output_path = runtime_dir / f"runtime-warmup-{index}.mp4"
                metrics = self.render(audio_path, output_path)
                total_ms += int(metrics["total_ms"])
                output_path.unlink(missing_ok=True)
            return {**metrics, "total_ms": total_ms, "iterations": 2}
        finally:
            audio_path.unlink(missing_ok=True)

    def _encoder_command(
        self,
        audio_path: Path,
        output_path: Path,
        width: int,
        height: int,
    ) -> list[str]:
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s:v",
            f"{width}x{height}",
            "-r",
            str(self.args.fps),
            "-i",
            "pipe:0",
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            self.encoder,
        ]
        if self.encoder == "h264_nvenc":
            command.extend(["-preset", "p1", "-tune", "ll"])
        else:
            command.extend(["-preset", "ultrafast"])
        command.extend(
            [
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )
        return command

    def render(self, audio_path: Path, output_path: Path) -> dict[str, Any]:
        started = time.perf_counter()
        realtime = self.realtime
        feature_started = time.perf_counter()
        whisper_input_features, librosa_length = (
            realtime.audio_processor.get_audio_feature(
                str(audio_path),
                weight_dtype=realtime.weight_dtype,
            )
        )
        whisper_chunks = realtime.audio_processor.get_whisper_chunk(
            whisper_input_features,
            realtime.device,
            realtime.weight_dtype,
            realtime.whisper,
            librosa_length,
            fps=self.args.fps,
            audio_padding_length_left=self.args.audio_padding_length_left,
            audio_padding_length_right=self.args.audio_padding_length_right,
        )
        audio_feature_ms = round((time.perf_counter() - feature_started) * 1_000)
        video_num = len(whisper_chunks)
        if video_num == 0:
            raise RuntimeError("MuseTalk produced no audio feature frames.")

        frame = self.avatar.frame_list_cycle[0]
        height, width = frame.shape[:2]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.unlink(missing_ok=True)
        ffmpeg = subprocess.Popen(
            self._encoder_command(audio_path, output_path, width, height),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if ffmpeg.stdin is None:
            raise RuntimeError("Could not open the FFmpeg input pipe.")

        frame_queue: queue.Queue[Any] = queue.Queue(
            maxsize=max(2, self.args.batch_size * 2)
        )
        sentinel = object()
        encoder_error: list[BaseException] = []

        def blend_and_encode() -> None:
            index = 0
            try:
                while True:
                    generated = frame_queue.get()
                    if generated is sentinel:
                        break
                    bbox = self.avatar.coord_list_cycle[
                        index % len(self.avatar.coord_list_cycle)
                    ]
                    original = self.avatar.frame_list_cycle[
                        index % len(self.avatar.frame_list_cycle)
                    ].copy()
                    x1, y1, x2, y2 = bbox
                    resized = self.cv2.resize(
                        generated.astype(self.np.uint8),
                        (x2 - x1, y2 - y1),
                    )
                    mask = self.avatar.mask_list_cycle[
                        index % len(self.avatar.mask_list_cycle)
                    ]
                    mask_box = self.avatar.mask_coords_list_cycle[
                        index % len(self.avatar.mask_coords_list_cycle)
                    ]
                    combined = self.get_image_blending(
                        original,
                        resized,
                        bbox,
                        mask,
                        mask_box,
                    )
                    ffmpeg.stdin.write(combined.tobytes())
                    index += 1
            except BaseException as exc:  # propagate from the encoder thread
                encoder_error.append(exc)
            finally:
                try:
                    ffmpeg.stdin.close()
                except OSError:
                    pass

        encoder_thread = threading.Thread(
            target=blend_and_encode,
            name="musetalk-frame-encoder",
        )
        encoder_thread.start()
        inference_started = time.perf_counter()
        try:
            batches = self.datagen(
                whisper_chunks,
                self.avatar.input_latent_list_cycle,
                self.args.batch_size,
            )
            with self.torch.inference_mode():
                for whisper_batch, latent_batch in batches:
                    if encoder_error:
                        raise encoder_error[0]
                    audio_batch = realtime.pe(whisper_batch.to(self.device))
                    latent_batch = latent_batch.to(
                        device=self.device,
                        dtype=realtime.unet.model.dtype,
                    )
                    predicted = realtime.unet.model(
                        latent_batch,
                        realtime.timesteps,
                        encoder_hidden_states=audio_batch,
                    ).sample
                    predicted = predicted.to(
                        device=self.device,
                        dtype=realtime.vae.vae.dtype,
                    )
                    for generated in realtime.vae.decode_latents(predicted):
                        frame_queue.put(generated)
            self.torch.cuda.synchronize(self.device)
        finally:
            frame_queue.put(sentinel)
            encoder_thread.join()
        inference_ms = round((time.perf_counter() - inference_started) * 1_000)
        if encoder_error:
            raise encoder_error[0]

        stderr = ffmpeg.stderr.read() if ffmpeg.stderr is not None else b""
        return_code = ffmpeg.wait(timeout=30)
        if return_code != 0:
            raise RuntimeError(stderr.decode(errors="replace")[-1_000:])
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg completed without an MP4 output.")

        total_ms = round((time.perf_counter() - started) * 1_000)
        return {
            "status": "completed",
            "total_ms": total_ms,
            "audio_feature_ms": audio_feature_ms,
            "inference_and_encode_ms": inference_ms,
            "frames": video_num,
            "effective_fps": round(video_num / max(total_ms / 1_000, 0.001), 2),
            "video_encoder": self.encoder,
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--musetalk-root", required=True)
    parser.add_argument("--asset-root", required=True)
    parser.add_argument("--source-avatar", required=True)
    parser.add_argument("--unet-model-path", required=True)
    parser.add_argument("--unet-config", required=True)
    parser.add_argument("--version", choices=["v1", "v15"], default="v15")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--fps", type=int, default=25)
    parser.add_argument("--avatar-seconds", type=float, default=4)
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--bbox-shift", type=int, default=0)
    parser.add_argument("--extra-margin", type=int, default=10)
    parser.add_argument("--parsing-mode", default="jaw")
    parser.add_argument("--left-cheek-width", type=int, default=90)
    parser.add_argument("--right-cheek-width", type=int, default=90)
    parser.add_argument("--audio-padding-length-left", type=int, default=2)
    parser.add_argument("--audio-padding-length-right", type=int, default=2)
    parser.add_argument("--video-encoder", default="h264_nvenc")
    parser.add_argument("--ready-path", required=True)
    parser.add_argument("--use-float16", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    ready_path = Path(args.ready_path).resolve()
    try:
        renderer = PersistentRenderer(args)
        warmup_metrics = renderer.warm_up()
        _write_json(
            ready_path,
            {
                "status": "ready",
                "startup_ms": renderer.startup_ms,
                "warmup_ms": warmup_metrics["total_ms"],
                "video_encoder": renderer.encoder,
                "avatar_cache": renderer.avatar_cache,
            },
        )
    except BaseException as exc:
        _write_json(
            ready_path,
            {"status": "failed", "error": f"{type(exc).__name__}: {exc}"},
        )
        raise

    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get("command") == "shutdown":
                return 0
            if request.get("command") != "generate":
                continue
            result_path = Path(request["result_path"]).resolve()
            try:
                metrics = renderer.render(
                    Path(request["audio_path"]).resolve(),
                    Path(request["output_path"]).resolve(),
                )
                _write_json(result_path, metrics)
            except BaseException as exc:
                _write_json(
                    result_path,
                    {
                        "status": "failed",
                        "error_code": "musetalk_generation_failed",
                        "message": f"{type(exc).__name__}: {exc}",
                    },
                )
        except (json.JSONDecodeError, KeyError):
            continue
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
