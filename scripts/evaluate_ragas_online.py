"""Gemini judge로 Faithfulness·Response Relevancy를 평가한다."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI_SRC = ROOT / "ai" / "src"
if str(AI_SRC) not in sys.path:
    sys.path.insert(0, str(AI_SRC))

from lease_companion_ai.evaluation.ragas_online import (  # noqa: E402
    evaluate_ragas_llm_cases,
    load_ragas_llm_cases,
)
from lease_companion_ai.providers.gemini_embeddings import (  # noqa: E402
    GeminiEmbeddingProvider,
)
from lease_companion_ai.providers.ragas_gemini import GeminiRagasLLM  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data/evaluation/ragas_llm_test.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/evaluation/results/ragas_llm_metrics.json",
    )
    parser.add_argument(
        "--judge-model",
        default=os.getenv("GEMINI_MODEL_RAGAS_JUDGE", "gemini-3.5-flash"),
    )
    parser.add_argument(
        "--embedding-model",
        default="gemini-embedding-001",
    )
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY 또는 GOOGLE_API_KEY가 필요합니다.")
    os.environ.setdefault(
        "GEMINI_REQUESTS_PER_MINUTE",
        os.getenv("GEMINI_RAGAS_REQUESTS_PER_MINUTE", "5"),
    )

    from google import genai
    from ragas.metrics import Faithfulness, ResponseRelevancy

    client = genai.Client(api_key=api_key)
    llm = GeminiRagasLLM(
        client=client,
        model=args.judge_model,
    )
    embeddings = GeminiEmbeddingProvider(
        client=client,
    )
    try:
        report = evaluate_ragas_llm_cases(
            load_ragas_llm_cases(args.input),
            metrics=[
                Faithfulness(llm=llm),
                ResponseRelevancy(llm=llm, embeddings=embeddings),
            ],
            judge_model=f"gemini/{args.judge_model}",
            embedding_model=args.embedding_model,
            measured_at=date.today().isoformat(),
            ragas_version=version("ragas"),
        )
    finally:
        client.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "RAGAS LLM evaluation: "
        f"cases={report['evaluated_case_count']} "
        f"failures={report['failed_score_count']} output={args.output}"
    )


if __name__ == "__main__":
    main()
