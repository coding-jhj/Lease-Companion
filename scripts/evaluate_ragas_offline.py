"""실제 provider 호출 없이 RAGAS ID 기반 검색 지표를 기록한다."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from lease_companion_ai.evaluation.ragas_offline import evaluate_ragas_offline

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/evaluation/results/ragas_offline_metrics.json"


def main() -> None:
    report = evaluate_ragas_offline(ROOT, measured_at=date.today())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(
        "RAGAS offline evaluation: "
        f"general_p={report.general_rag_sources.macro_context_precision:.4f} "
        f"general_r={report.general_rag_sources.macro_context_recall:.4f} "
        f"special_source_p={report.special_clause_sources.macro_context_precision:.4f} "
        f"special_source_r={report.special_clause_sources.macro_context_recall:.4f} "
        f"special_section_p={report.special_clause_sections.macro_context_precision:.4f} "
        f"special_section_r={report.special_clause_sections.macro_context_recall:.4f} "
        f"output={OUTPUT}"
    )


if __name__ == "__main__":
    main()
