from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_report_cli_writes_json_csv_and_svg_without_external_calls(
    tmp_path: Path,
) -> None:
    source = tmp_path / "calls.jsonl"
    source.write_text(
        json.dumps(
            {
                "timestamp": "2026-07-28T12:00:00+00:00",
                "provider": "cohere",
                "model": "rerank-v4.0-pro",
                "task": "rerank",
                "status": "success",
                "attempt": 1,
                "latency_ms": 300,
                "ttfb_ms": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "search_units": 1,
                "estimated_cost": None,
                "currency": None,
                "pricing_version": None,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "report"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_provider_report.py"),
            "--input",
            str(source),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "provider-summary.json").exists()
    with (output_dir / "provider-summary.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["model"] == "rerank-v4.0-pro"
    svg = (output_dir / "provider-latency.svg").read_text(encoding="utf-8")
    assert "<svg" in svg
    assert "rerank-v4.0-pro" in svg
    ttfb_svg = (output_dir / "provider-ttfb.svg").read_text(encoding="utf-8")
    assert "<svg" in ttfb_svg
    assert "TTFB 측정값 없음" in ttfb_svg
