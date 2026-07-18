from datetime import date

import pytest

from lease_companion_ai.evaluation.retrieval import (
    RetrievalEvaluationCase,
    evaluate_retrieval,
)
from lease_companion_ai.rag.models import RetrievalQuery
from lease_companion_ai.rag.service import get_default_evidence_service
from lease_companion_ai.schemas.unified import RuleStatus


def _case(case_id: str) -> RetrievalEvaluationCase:
    return RetrievalEvaluationCase(
        case_id=case_id,
        query=RetrievalQuery(
            rule_id="R08",
            rule_name="보증금 반환 시점 조건",
            status=RuleStatus.UNCLEAR,
        ),
        expected_source_ids=("SRC-HTA-LAW",),
    )


def test_retrieval_metrics_measure_official_local_corpus():
    metrics = evaluate_retrieval(
        [_case("CASE-001")],
        get_default_evidence_service(),
        split="dev",
        measured_at=date(2026, 7, 17),
        config_version="rag-local-v1",
    )

    assert metrics.query_count == 1
    assert metrics.top_k_answer_inclusion_count == 1
    assert metrics.unofficial_source_exposure_count == 0
    assert metrics.complete_citation_count == metrics.citation_count


def test_dev_and_test_ids_cannot_mix():
    with pytest.raises(ValueError, match="TEST"):
        evaluate_retrieval(
            [_case("TEST-001")],
            get_default_evidence_service(),
            split="dev",
            measured_at=date(2026, 7, 17),
            config_version="rag-local-v1",
        )
