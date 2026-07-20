"""A 로컬 평가 러너의 회귀 계약."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from lease_companion_ai.evaluation.offline import evaluate_offline_pipeline

ROOT = Path(__file__).resolve().parents[3]


def test_offline_pipeline_measures_all_a_dimensions_without_provider_calls():
    report = evaluate_offline_pipeline(
        ROOT,
        measured_at=date(2026, 7, 18),
    )

    assert report.split == "test"
    assert report.extraction.case_count == 10
    assert report.extraction.schema_valid_count == 20
    assert report.extraction.unreadable_representation_valid_rate == 1.0
    assert report.corrections.pass_rate == 1.0
    assert report.rules.rule_count == 100
    assert report.judgments.case_count == 47
    assert report.judgments.judgment_count == 12
    assert report.judgments.status.accuracy == 1.0
    assert report.judgments.urgency.accuracy == 1.0
    assert report.retrieval.case_count == 10
    assert report.retrieval.locally_available_expected_source_count == 15
    assert report.retrieval.locally_available_expected_source_hit_count == 15
    assert report.retrieval.locally_available_expected_source_recall == 1.0
    assert report.retrieval.failure_reason_counts == {
        "expected_source_not_locally_available": 24,
        "allowlist_filtered": 0,
        "bm25_candidate_miss": 0,
        "outside_top_k": 0,
    }
    assert sum(report.retrieval.failure_reason_counts.values()) == (
        report.retrieval.expected_source_count
        - report.retrieval.expected_source_hit_count
    )
    assert report.judgment_retrieval.query_count > 0
    assert report.judgment_retrieval.locally_available_expected_source_count == 30
    assert report.judgment_retrieval.retrieved_expected_source_count == 30
    assert report.judgment_retrieval.expected_source_recall == 30 / 41
    assert report.judgment_retrieval.unofficial_source_exposure_count == 0
    assert report.generation.case_count == 10
    assert report.generation.schema_valid_rate == 1.0
    assert report.generation.analysis_immutable_rate == 1.0
    assert report.generation.trigger_coverage_rate == 1.0
    assert report.generation.active_judgment_count > 0
    assert report.generation.judgment_trigger_coverage_rate == 1.0
    assert report.generation.grounding_violation_count == 0
    assert report.generation.judgment_grounding_violation_count == 0
    assert report.generation.prohibited_claim_count == 0
    assert report.generation.provider_call_count == 0
    assert report.guardrail.expected_reason_match_rate == 1.0
    assert report.guardrail.rule_case_count == 3
    assert report.guardrail.judgment_case_count == 3
    assert report.guardrail.false_negative_count == 0
    assert report.pii.case_count == 5
    assert report.pii.tokenization_pass_rate == 1.0
    assert report.pii.restoration_pass_rate == 1.0
    assert report.end_to_end.completion_rate == 1.0
    assert report.end_to_end.external_provider_call_count == 0
    assert report.end_to_end.external_provider_cost_krw == 0


def test_offline_report_is_json_serializable():
    report = evaluate_offline_pipeline(ROOT, measured_at=date(2026, 7, 18))

    payload = report.to_dict()

    assert payload["measured_at"] == "2026-07-18"
    assert payload["generation"]["subjective_quality"].startswith("not_measured:")
