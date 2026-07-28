from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_ppt_metrics_cli_generates_evaluation_and_cycle_assets(tmp_path: Path) -> None:
    offline = {
        "extraction": {"accuracy": 1.0, "field_count": 240},
        "rules": {"status": {"accuracy": 1.0}},
        "judgments": {"status": {"accuracy": 1.0}},
        "end_to_end": {"completion_rate": 1.0, "case_count": 10},
    }
    ragas_offline = {
        "general_rag_sources": {
            "macro_context_precision": 1.0,
            "macro_context_recall": 1.0,
        },
        "special_clause_sources": {
            "macro_context_precision": 0.9167,
            "macro_context_recall": 0.9167,
        },
        "special_clause_sections": {
            "macro_context_precision": 0.6667,
            "macro_context_recall": 0.6667,
        },
    }
    ragas_online = {
        "evaluated_case_count": 3,
        "metrics": {
            "faithfulness": {"macro_average": 0.7222},
            "answer_relevancy": {"macro_average": 0.8247},
        },
    }
    actual = {
        "mode": "actual_contract",
        "call_count": 10,
        "known_cost_usd": 0.12,
        "wall_clock_ms": 1000,
        "input_tokens": 100,
        "output_tokens": 50,
        "search_units": 2,
        "outcome": {"classification_method": "provider"},
    }
    simulation = {
        "mode": "simulation",
        "call_count": 6,
        "known_cost_usd": 0.02,
        "wall_clock_ms": 500,
        "input_tokens": 80,
        "output_tokens": 20,
        "search_units": 0,
        "outcome": {"completed": True},
    }
    extraction_gemini = {
        "accuracy": 0.9125,
        "field_count": 240,
        "local_fallback_case_count": 0,
        "rules_on_provider_extraction": {
            "status_accuracy": 0.87,
            "urgency_accuracy": 0.6296,
        },
    }
    retrieval_provider = {
        "macro_context_recall": 1.0,
        "special_clauses": {
            "source_macro_context_precision": 0.9167,
            "section_macro_context_precision": 0.7778,
        },
    }
    inputs = {
        "extraction-gemini.json": extraction_gemini,
        "retrieval-provider.json": retrieval_provider,
        "offline.json": offline,
        "ragas-offline.json": ragas_offline,
        "ragas-online.json": ragas_online,
        "actual.json": actual,
        "simulation.json": simulation,
    }
    for name, payload in inputs.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "ppt"

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/generate_ppt_metrics_assets.py"),
            "--offline",
            str(tmp_path / "offline.json"),
            "--ragas-offline",
            str(tmp_path / "ragas-offline.json"),
            "--ragas-online",
            str(tmp_path / "ragas-online.json"),
            "--extraction-gemini",
            str(tmp_path / "extraction-gemini.json"),
            "--retrieval-provider",
            str(tmp_path / "retrieval-provider.json"),
            "--actual-cycle",
            str(tmp_path / "actual.json"),
            "--simulation-cycle",
            str(tmp_path / "simulation.json"),
            "--output-dir",
            str(output),
        ],
        check=True,
    )

    assert "Faithfulness" in (output / "02-evaluation-summary.svg").read_text(
        encoding="utf-8"
    )
    cycle_svg = (output / "03-mode-cycle-cost.svg").read_text(encoding="utf-8")
    assert "실제 계약 점검" in cycle_svg
    assert "시뮬레이션" in cycle_svg
    assert (output / "02-evaluation-summary.csv").exists()
    assert (output / "03-mode-cycle-summary.csv").exists()
