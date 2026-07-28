from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_cycle_collection_cli_has_distinct_actual_and_simulation_paths() -> None:
    source = (ROOT / "scripts/collect_mode_cycle_metrics.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    assert "run_actual_contract_cycle" in names
    assert "run_simulation_cycle" in names
    assert "CohereRerankProvider" in names
    assert "GeminiPracticeProvider" in names
    assert "GeminiPracticeDialogueProvider" in names
    assert "raw_text" not in source
