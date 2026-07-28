"""운영 경로(Gemini 구조화)로 test 10건을 추출해 goldset과 대조한다.

`evaluate_ai_pipeline.py`는 외부 호출 없이 로컬 정규식 fallback을 재는 기준선이다.
이 스크립트는 같은 goldset·같은 채점기를 쓰되 추출만 실제 provider 경로로 바꾼다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AI_SRC = ROOT / "ai" / "src"
if str(AI_SRC) not in sys.path:
    sys.path.insert(0, str(AI_SRC))

from lease_companion_ai.evaluation.offline import (  # noqa: E402
    _evaluate_extraction,
    _evaluate_rules,
    _read_jsonl,
)
from lease_companion_ai.pipelines.minimum_mvp import extract_documents  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/evaluation/results/extraction_gemini_metrics.json",
    )
    parser.add_argument("--metrics-jsonl", type=Path)
    args = parser.parse_args()
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        raise SystemExit("GEMINI_API_KEY가 필요합니다.")
    if args.metrics_jsonl:
        os.environ["PROVIDER_METRICS_JSONL"] = str(args.metrics_jsonl)

    base = ROOT / "data/evaluation/end-to-end"
    records = _read_jsonl(base / "final_testset_extraction.jsonl")

    predictions: dict[str, dict[str, dict[str, Any]]] = {}
    per_case: list[dict[str, Any]] = []
    for record in records:
        contract_path = base / "contracts" / record["contract_file"]
        registry_path = base / "registry-records" / record["registry_file"]
        result = extract_documents(
            contract_path.read_bytes(),
            contract_path.name,
            registry_path.read_bytes(),
            registry_path.name,
        )
        predictions[record["case_id"]] = {
            "contract": result["contract"].get("fields", {}),
            "registry": result["registry"].get("fields", {}),
        }
        # 라우팅이 로컬 폴백으로 내려갔다면 그 케이스는 Gemini 값이 아니다.
        fallbacks = [
            decision
            for section in ("contract", "registry")
            for decision in result[section].get("routing_decisions", [])
            if decision.get("fallback_used")
        ]
        per_case.append(
            {
                "case_id": record["case_id"],
                "read_ok": bool(
                    result["contract"].get("read_ok")
                    and result["registry"].get("read_ok")
                ),
                "local_fallback_used": bool(fallbacks),
                "fallback_reasons": [d.get("reason") for d in fallbacks],
            }
        )

    metrics = _evaluate_extraction(records, predictions)
    # 규칙 엔진은 결정론이지만 입력이 provider 추출값이어야 실제 흐름과 같다.
    rule_records = _read_jsonl(base / "final_testset_rule.jsonl")
    rules = _evaluate_rules(rule_records, predictions)
    payload = {
        "measured_at": date.today().isoformat(),
        "split": "test",
        "extraction_path": "gemini_provider",
        "model": os.getenv("GEMINI_MODEL_EXTRACTION", "gemini-3.5-flash"),
        "case_count": metrics.case_count,
        "field_count": metrics.field_count,
        "matched_count": metrics.matched_count,
        "accuracy": metrics.accuracy,
        "rules_on_provider_extraction": {
            "status_accuracy": rules.status.accuracy,
            "status_matched_count": rules.status.matched_count,
            "status_item_count": rules.status.item_count,
            "urgency_accuracy": rules.urgency.accuracy,
            "urgency_matched_count": rules.urgency.matched_count,
            "urgency_item_count": rules.urgency.item_count,
        },
        "local_fallback_case_count": sum(
            1 for case in per_case if case["local_fallback_used"]
        ),
        "per_case": per_case,
        "per_field": metrics.per_field,
        "limitations": [
            "합성 test 10건 기준이며 실제 계약서 일반화 성능이 아닙니다.",
            "로컬 폴백이 사용된 케이스가 있으면 그 값은 provider 성능이 아닙니다.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"gemini extraction: {metrics.matched_count}/{metrics.field_count} "
        f"= {metrics.accuracy:.4f} | rules: {rules.status.matched_count}/"
        f"{rules.status.item_count} = {rules.status.accuracy:.4f} | "
        f"local_fallback_cases={payload['local_fallback_case_count']} | "
        f"output={args.output}"
    )


if __name__ == "__main__":
    main()
