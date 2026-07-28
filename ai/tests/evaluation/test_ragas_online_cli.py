from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_online_ragas_cli_uses_current_google_genai_adapters() -> None:
    path = ROOT / "scripts" / "evaluate_ragas_online.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }

    assert "GeminiRagasLLM" in names
    assert "GeminiEmbeddingProvider" in names
    assert "Faithfulness" in names
    assert "ResponseRelevancy" in names
    assert "GEMINI_API_KEY" in source
