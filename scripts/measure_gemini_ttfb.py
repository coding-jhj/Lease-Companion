"""합성 prompt로 Gemini stream 실제 TTFB를 반복 측정한다."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI_SRC = ROOT / "ai" / "src"
if str(AI_SRC) not in sys.path:
    sys.path.insert(0, str(AI_SRC))

from lease_companion_ai.evaluation.provider_metrics import (  # noqa: E402
    JsonlMetricSink,
    metric_recorder_from_env,
)
from lease_companion_ai.providers.gemini_gateway import (  # noqa: E402
    GeminiCallPolicy,
    GeminiGateway,
    gemini_http_options,
)

_SYNTHETIC_PROMPT = (
    "개인정보가 없는 성능 측정 요청입니다. "
    "대한민국 주택 임대차 계약 전 확인 항목 세 가지를 짧게 나열하세요."
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--model",
        default=os.getenv("GEMINI_MODEL_GENERATION", "gemini-3.5-flash"),
    )
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--requests-per-minute", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if args.runs <= 0:
        parser.error("--runs는 양수여야 합니다.")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds는 양수여야 합니다.")
    if args.requests_per_minute <= 0:
        parser.error("--requests-per-minute은 양수여야 합니다.")

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY 또는 GOOGLE_API_KEY가 필요합니다.")

    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=api_key,
        http_options=gemini_http_options(int(args.timeout_seconds * 1_000)),
    )
    os.environ["PROVIDER_METRICS_JSONL"] = str(args.output)
    metric_sink = metric_recorder_from_env() or JsonlMetricSink(args.output).write
    gateway = GeminiGateway(metric_sink=metric_sink)
    os.environ["GEMINI_REQUESTS_PER_MINUTE"] = str(args.requests_per_minute)
    wait_budget = 60.0 / args.requests_per_minute + 5.0
    try:
        for index in range(1, args.runs + 1):
            chunks = gateway.call_stream(
                task="ttfb_measurement",
                model=args.model,
                policy=GeminiCallPolicy(
                    max_attempts=1,
                    max_total_wait_seconds=wait_budget,
                ),
                operation=lambda: client.models.generate_content_stream(
                    model=args.model,
                    contents=_SYNTHETIC_PROMPT,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        max_output_tokens=128,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                ),
            )
            print(f"TTFB run {index}/{args.runs}: chunks={len(chunks)}")
    finally:
        client.close()
    print(f"TTFB metrics: {args.output}")


if __name__ == "__main__":
    main()
