from datetime import date

import pytest

from lease_companion_ai.evaluation.retrieval import (
    RetrievalEvaluationCase,
    evaluate_retrieval,
)
from lease_companion_ai.rag.models import (
    RagChunk,
    RagSourceMetadata,
    RetrievalHit,
    RetrievalQuery,
)
from lease_companion_ai.rag.service import (
    EvidenceRetrievalService,
    get_default_evidence_service,
)
from lease_companion_ai.schemas.unified import RuleStatus


def _case(
    case_id: str,
    *,
    rule_id: str = "R08",
    expected_source_id: str = "SRC-HTA-LAW",
    allowed_source_ids: tuple[str, ...] | None = None,
) -> RetrievalEvaluationCase:
    return RetrievalEvaluationCase(
        case_id=case_id,
        query=RetrievalQuery(
            rule_id=rule_id,
            rule_name="보증금 반환 시점 조건",
            status=RuleStatus.UNCLEAR,
        ),
        expected_source_ids=(expected_source_id,),
        allowed_source_ids=allowed_source_ids or (expected_source_id,),
    )


def _hit(source_id: str, rank: int) -> RetrievalHit:
    digest = f"{rank:064x}"
    metadata = RagSourceMetadata(
        source_id=source_id,
        document_title=f"{source_id} 문서",
        institution="평가기관",
        document_type="법령",
        article_or_section="평가 조항",
        effective_date="2026-07-18",
        source_url=f"https://example.go.kr/{source_id}",
        collected_date=date(2026, 7, 18),
        source_sha256=digest,
        usage_terms="합성 평가 fixture",
    )
    return RetrievalHit(
        chunk=RagChunk(
            chunk_id=f"{source_id}:{digest}",
            metadata=metadata,
            section="평가 조항",
            ordinal=rank - 1,
            text=f"{source_id} 평가 본문",
        ),
        score=float(100 - rank),
        rank=rank,
        retrieval_method="bm25",
    )


class _StubRetriever:
    def __init__(self, hits_by_rule: dict[str, tuple[RetrievalHit, ...]]) -> None:
        self._hits_by_rule = hits_by_rule

    def search(
        self, query: RetrievalQuery, *, top_k: int = 20
    ) -> list[RetrievalHit]:
        return list(self._hits_by_rule.get(query.rule_id, ())[:top_k])


def test_retrieval_metrics_measure_official_local_corpus():
    metrics = evaluate_retrieval(
        [_case("CASE-001")],
        get_default_evidence_service(),
        split="dev",
        measured_at=date(2026, 7, 17),
        config_version="rag-local-v1",
        locally_available_source_ids={"SRC-HTA-LAW", "SRC-HTA-DECREE"},
    )

    assert metrics.query_count == 1
    assert metrics.top_k_answer_inclusion_count == 1
    assert metrics.locally_available_expected_source_count == 1
    assert metrics.locally_available_expected_source_hit_count == 1
    assert metrics.locally_available_expected_source_recall == 1.0
    assert sum(metrics.failure_reason_counts.values()) == 0
    assert metrics.locally_unavailable_expected_source_ids == ()
    assert metrics.actionable_failure_diagnostics == ()
    assert metrics.unofficial_source_exposure_count == 0
    assert metrics.complete_citation_count == metrics.citation_count


def test_retrieval_failures_are_partitioned_by_actionable_root_cause():
    top_k_hits = tuple(
        _hit(f"SRC-FILLER-{rank}", rank) for rank in range(1, 6)
    ) + (_hit("SRC-TOP-K", 6),)
    service = EvidenceRetrievalService(
        _StubRetriever({"R04": top_k_hits}),
        judgment_source_ids={},
    )
    cases = [
        _case("CASE-001", rule_id="R01", expected_source_id="SRC-NO-LOCAL"),
        _case("CASE-001", rule_id="R02", expected_source_id="SRC-BM25-MISS"),
        _case(
            "CASE-001",
            rule_id="R03",
            expected_source_id="SRC-NOT-ALLOWED",
            allowed_source_ids=("SRC-OTHER",),
        ),
        _case("CASE-001", rule_id="R04", expected_source_id="SRC-TOP-K"),
    ]

    metrics = evaluate_retrieval(
        cases,
        service,
        split="dev",
        measured_at=date(2026, 7, 18),
        config_version="diagnostic-test",
        locally_available_source_ids={
            "SRC-BM25-MISS",
            "SRC-NOT-ALLOWED",
            "SRC-TOP-K",
        },
        top_k=5,
        candidate_k=20,
    )

    assert metrics.locally_available_expected_source_count == 3
    assert metrics.locally_available_expected_source_hit_count == 0
    assert metrics.locally_available_expected_source_recall == 0.0
    assert metrics.failure_reason_counts == {
        "expected_source_not_locally_available": 1,
        "allowlist_filtered": 1,
        "bm25_candidate_miss": 1,
        "outside_top_k": 1,
    }
    assert metrics.locally_unavailable_expected_source_ids == ("SRC-NO-LOCAL",)
    assert {
        diagnostic.expected_source_id: diagnostic.reason
        for diagnostic in metrics.actionable_failure_diagnostics
    } == {
        "SRC-NOT-ALLOWED": "allowlist_filtered",
        "SRC-BM25-MISS": "bm25_candidate_miss",
        "SRC-TOP-K": "outside_top_k",
    }


def test_dev_and_test_ids_cannot_mix():
    with pytest.raises(ValueError, match="TEST"):
        evaluate_retrieval(
            [_case("TEST-001")],
            get_default_evidence_service(),
            split="dev",
            measured_at=date(2026, 7, 17),
            config_version="rag-local-v1",
            locally_available_source_ids={"SRC-HTA-LAW"},
        )
