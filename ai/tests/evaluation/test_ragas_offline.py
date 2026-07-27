"""RAGAS ID 기반 오프라인 검색 평가 회귀 계약."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from lease_companion_ai.evaluation.ragas_offline import (
    RagasIdCase,
    evaluate_ragas_offline,
    score_ragas_id_cases,
)

ROOT = Path(__file__).resolve().parents[3]


def test_ragas_id_scores_use_set_based_precision_and_recall():
    summary = score_ragas_id_cases(
        [
            RagasIdCase(
                case_id="CASE-001",
                retrieved_context_ids=("SRC-A", "SRC-A", "SRC-B"),
                reference_context_ids=("SRC-A", "SRC-C"),
            ),
            RagasIdCase(
                case_id="CASE-NONE",
                retrieved_context_ids=(),
                reference_context_ids=(),
            ),
        ],
        scope="unit",
        top_k=3,
    )

    assert summary.evaluated_case_count == 1
    assert summary.excluded_no_reference_case_count == 1
    assert summary.macro_context_precision == 0.5
    assert summary.macro_context_recall == 0.5


def test_ragas_offline_measures_general_and_special_rag_without_provider_calls():
    report = evaluate_ragas_offline(ROOT, measured_at=date(2026, 7, 27))

    assert report.ragas_version == "0.3.9"
    assert report.general_rag_sources.evaluated_case_count == 27
    assert report.general_rag_sources.macro_context_precision == 1.0
    assert report.general_rag_sources.macro_context_recall == 1.0
    assert report.special_clause_sources.evaluated_case_count == 6
    assert report.special_clause_sources.excluded_no_reference_case_count == 1
    assert report.special_clause_sources.macro_context_precision == pytest.approx(11 / 12)
    assert report.special_clause_sources.macro_context_recall == pytest.approx(11 / 12)
    assert report.special_clause_sections.evaluated_case_count == 6
    assert report.special_clause_sections.excluded_no_reference_case_count == 1
    assert report.special_clause_sections.macro_context_precision == pytest.approx(2 / 3)
    assert report.special_clause_sections.macro_context_recall == pytest.approx(2 / 3)
    assert report.external_provider_call_count == 0


def test_ragas_id_score_rejects_invalid_input():
    with pytest.raises(ValueError, match="평가 사례"):
        score_ragas_id_cases([], scope="empty", top_k=5)
    with pytest.raises(ValueError, match="top_k"):
        score_ragas_id_cases(
            [RagasIdCase("CASE-001", ("SRC-A",), ("SRC-A",))],
            scope="invalid",
            top_k=0,
        )
