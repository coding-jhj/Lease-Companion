"""A 로컬 결정론적 평가를 실행하고 test 기준선을 JSON으로 기록한다."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from lease_companion_ai.evaluation.offline import evaluate_offline_pipeline

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "evaluation" / "results" / "offline_test_metrics.json"


def main() -> None:
    report = evaluate_offline_pipeline(ROOT, measured_at=date.today())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(
        "A offline evaluation: "
        f"e2e={report.end_to_end.completed_case_count}/{report.end_to_end.case_count} "
        f"special_catalog={report.special_clauses.catalog_exact_match_count}/"
        f"{report.special_clauses.catalog_case_count} "
        f"special_source_top3={report.special_clauses.source_top3_hit_count}/"
        f"{report.special_clauses.expected_source_count} "
        f"special_section_top3={report.special_clauses.section_top3_hit_count}/"
        f"{report.special_clauses.expected_section_count} "
        f"output={OUTPUT}"
    )


if __name__ == "__main__":
    main()
