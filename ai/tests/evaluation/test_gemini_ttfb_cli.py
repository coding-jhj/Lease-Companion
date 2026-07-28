from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_ttfb_cli_uses_streaming_api_and_synthetic_prompt_only() -> None:
    path = ROOT / "scripts" / "measure_gemini_ttfb.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "generate_content_stream" in attributes
    assert "generate_content" not in attributes
    assert "metric_recorder_from_env" in {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    assert "contract_id" not in source
    assert "document_id" not in source
