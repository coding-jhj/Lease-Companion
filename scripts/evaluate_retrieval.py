"""로컬 공식 코퍼스로 dev/test retrieval 지표를 각각 기록한다."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Literal

from lease_companion_ai.evaluation.retrieval import evaluate_retrieval, load_gold_cases
from lease_companion_ai.rag.service import build_evidence_service, load_local_official_chunks


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "rag" / "evaluation"


def main(split: Literal["dev", "test", "all"] = "all") -> None:
    chunks = load_local_official_chunks(ROOT)
    service = build_evidence_service(chunks)
    locally_available_source_ids = {
        chunk.metadata.source_id for chunk in chunks
    }
    rule_spec = ROOT / "data" / "rules" / "rule_spec.csv"
    rule_evidence_map = ROOT / "data" / "rules" / "rule_evidence_map.csv"
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
    selected = inputs.items() if split == "all" else ((split, inputs[split]),)
    for selected_split, (rag_goldset, rule_goldset) in selected:
        cases = load_gold_cases(
            rag_goldset, rule_goldset, rule_spec, rule_evidence_map
        )
        metrics = evaluate_retrieval(
            cases,
            service,
            split=selected_split,
            measured_at=date.today(),
            config_version="local-bm25-chunk-v1",
            locally_available_source_ids=locally_available_source_ids,
            top_k=5,
        )
        path = OUTPUT / f"{selected_split}_metrics.json"
        path.write_text(
            json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"{selected_split}: queries={metrics.query_count} output={path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test", "all"), default="all")
    args = parser.parse_args()
    main(args.split)
