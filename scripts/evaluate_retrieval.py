"""로컬 공식 코퍼스로 dev/test retrieval 지표를 각각 기록한다."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

from lease_companion_ai.evaluation.retrieval import evaluate_retrieval, load_gold_cases
from lease_companion_ai.rag.service import build_evidence_service, load_local_official_chunks


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "rag" / "evaluation"


def main() -> None:
    service = build_evidence_service(load_local_official_chunks(ROOT))
    rule_spec = ROOT / "data" / "rules" / "rule_spec.csv"
    inputs: dict[Literal["dev", "test"], tuple[Path, Path]] = {
        "dev": (
            ROOT / "data" / "sample" / "expected-results" / "rag_goldset.jsonl",
            ROOT / "data" / "sample" / "expected-results" / "rule_goldset.jsonl",
        ),
        "test": (
            ROOT / "data" / "evaluation" / "end-to-end" / "final_testset_rag.jsonl",
            ROOT / "data" / "evaluation" / "end-to-end" / "final_testset_rule.jsonl",
        ),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for split, (rag_goldset, rule_goldset) in inputs.items():
        cases = load_gold_cases(rag_goldset, rule_goldset, rule_spec)
        metrics = evaluate_retrieval(
            cases,
            service,
            split=split,
            measured_at=date.today(),
            config_version="local-bm25-chunk-v1",
            top_k=5,
        )
        path = OUTPUT / f"{split}_metrics.json"
        path.write_text(
            json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"{split}: queries={metrics.query_count} output={path}")


if __name__ == "__main__":
    main()
