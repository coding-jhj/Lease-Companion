"""Provider JSONL 로그를 발표용 JSON·CSV·SVG 자료로 변환한다."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI_SRC = ROOT / "ai" / "src"
if str(AI_SRC) not in sys.path:
    sys.path.insert(0, str(AI_SRC))

from lease_companion_ai.evaluation.provider_metrics import (  # noqa: E402
    build_provider_report,
    load_jsonl_metrics,
)


def _write_svg(
    rows: list[dict[str, object]],
    path: Path,
    *,
    value_key: str = "average_latency_ms",
    title: str = "Provider 평균 응답시간 (ms)",
    empty_message: str = "측정값 없음",
) -> None:
    width = 960
    row_height = 72
    height = 100 + max(1, len(rows)) * row_height
    measured = [row for row in rows if row.get(value_key) is not None]
    maximum = max((int(row[value_key]) for row in measured), default=1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="30" y="38" font-family="sans-serif" font-size="24" '
        f'font-weight="700">{title}</text>',
    ]
    if not measured:
        parts.append(
            '<text x="30" y="90" font-family="sans-serif" font-size="18" '
            f'fill="#6b7280">{empty_message}</text>'
        )
    for index, row in enumerate(measured):
        y = 70 + index * row_height
        label = f'{row["provider"]} / {row["model"]}'
        value = int(row[value_key])
        bar_width = round(600 * value / maximum)
        parts.extend(
            [
                f'<text x="30" y="{y + 20}" font-family="sans-serif" '
                f'font-size="16">{label}</text>',
                f'<rect x="300" y="{y}" width="{bar_width}" height="30" '
                'rx="4" fill="#4f46e5"/>',
                f'<text x="{310 + bar_width}" y="{y + 21}" '
                f'font-family="sans-serif" font-size="15">{value}</text>',
            ]
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    report = build_provider_report(load_jsonl_metrics(args.input))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "provider-summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    rows = report["models"]
    with (args.output_dir / "provider-summary.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        fieldnames = list(rows[0].keys()) if rows else ["provider", "model"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    _write_svg(rows, args.output_dir / "provider-latency.svg")
    _write_svg(
        rows,
        args.output_dir / "provider-ttfb.svg",
        value_key="average_ttfb_ms",
        title="Gemini 평균 TTFB (ms)",
        empty_message="TTFB 측정값 없음",
    )
    print(f"provider report: calls={report['call_count']} output={args.output_dir}")


if __name__ == "__main__":
    main()
