from __future__ import annotations

from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.rag.indexing.chunker import chunk_sections
from lease_companion_ai.rag.models import JudgmentRetrievalQuery, RetrievalHit
from lease_companion_ai.rag.service import (
    EvidenceRetrievalService,
    build_evidence_service,
    load_judgment_search_contexts,
    load_judgment_source_ids,
    load_local_official_chunks,
)
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    ContractContext,
    JudgmentResult,
)


class _StaticRetriever:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits

    def search(self, _query, *, top_k=20):
        return self.hits[:top_k]


class _FailedRetriever:
    def search(self, _query, *, top_k=20):
        raise ProviderError("provider unavailable")


def _judgments() -> list[JudgmentResult]:
    statuses = {
        "J01": "불일치",
        "J02": "일치",
        "J03": "적용 제외",
        "J04": "적용 제외",
        "J05": "일치",
        "J06": "명확",
        "J07": "일치",
        "J08": "일치",
        "J09": "명확",
        "J10": "명확",
        "J11": "명확",
        "J12": "명확",
    }
    return [
        JudgmentResult(
            judgment_id=judgment_id,
            judgment_name=f"{judgment_id} 판정",
            status=status,
            urgency="즉시 확인" if judgment_id == "J01" else "계약 전 확인",
            triggers_actions=judgment_id == "J01",
            reason=f"{judgment_id} 이유",
            question="확인 질문" if judgment_id == "J01" else None,
            recommended_actions=["확인 행동"] if judgment_id == "J01" else [],
            limitations="판정 한계",
        )
        for judgment_id, status in statuses.items()
    ]


def test_enrichment_preserves_rule_fields_and_adds_only_searched_official_sources():
    from lease_companion_ai.rag.service import get_default_evidence_service
    from lease_companion_ai.pipelines.minimum_mvp import analyze_verified_fields

    results = analyze_verified_fields(
        {
            "landlord_name": "임대인",
            "property_address": "가상 주소 1",
            "account_holder": "다른 명의",
            "deposit_return_condition": "명확",
            "repair_responsibility": "명확",
            "rights_change_clause_present": True,
        },
        {
            "owner_names": ["소유자"],
            "property_address": "가상 주소 1",
            "issue_date": "2026-07-01",
            "mortgage_present": True,
            "seizure_present": False,
            "provisional_seizure_present": False,
            "trust_present": False,
        },
        ContractContext(
            contract_id=1,
            contract_type="전세",
            contract_stage="계약금 입금 전",
            deposit_paid=False,
            signed=False,
            is_proxy_contract=False,
        ),
    )
    analysis = AnalysisRunResult(
        analysis_run_id="RUN-EVIDENCE",
        input_snapshot_id="SNAP-EVIDENCE",
        contract_id=1,
        results=results,
    )
    baseline = analysis.model_copy(
        update={
            "results": [
                result.model_copy(update={"evidence_sources": []})
                for result in analysis.results
            ]
        }
    )
    enriched = get_default_evidence_service().enrich(
        AnalysisRunResult.model_validate(baseline.model_dump())
    )

    before = {
        result.rule_id: result.model_dump(exclude={"evidence_sources"})
        for result in baseline.results
    }
    after = {
        result.rule_id: result.model_dump(exclude={"evidence_sources"})
        for result in enriched.results
    }
    assert after == before
    assert any(result.evidence_sources for result in enriched.results)
    assert all(
        not result.evidence_sources
        for result in enriched.results
        if not result.triggers_actions
    )


def test_total_provider_failure_returns_empty_evidence():
    service = EvidenceRetrievalService(_FailedRetriever())
    from lease_companion_ai.rag.models import RetrievalQuery
    from lease_companion_ai.schemas.unified import RuleStatus

    result = service.search(
        RetrievalQuery(rule_id="R01", rule_name="소유자 확인", status=RuleStatus.CHECK_NEEDED)
    )
    assert result.hits == ()
    assert result.provider_fallback_used is True


def test_judgment_search_keeps_only_query_allowlisted_sources(source_metadata):
    allowed_metadata = source_metadata.model_copy(
        update={"source_id": "SRC-STD-LEASE"}
    )
    unrelated_metadata = source_metadata.model_copy(
        update={"source_id": "SRC-HTA-LAW"}
    )
    allowed_chunk = chunk_sections(allowed_metadata, [("허용", "임대차 표준계약서")])[0]
    unrelated_chunk = chunk_sections(unrelated_metadata, [("제외", "주택임대차보호법")])[0]
    hits = [
        RetrievalHit(
            chunk=unrelated_chunk,
            score=2.0,
            rank=1,
            retrieval_method="bm25",
        ),
        RetrievalHit(
            chunk=allowed_chunk,
            score=1.0,
            rank=2,
            retrieval_method="bm25",
        ),
    ]
    service = EvidenceRetrievalService(_StaticRetriever(hits))

    result = service.search(
        JudgmentRetrievalQuery(
            judgment_id="J01",
            judgment_name="계약서 임대인=등기 소유자",
            status="불일치",
            allowed_source_ids=("SRC-STD-LEASE",),
        )
    )

    assert [hit.chunk.metadata.source_id for hit in result.hits] == ["SRC-STD-LEASE"]


def test_judgment_enrichment_preserves_decision_and_uses_source_mapping(source_metadata):
    from lease_companion_ai.pipelines.minimum_mvp import analyze_verified_fields

    rules = analyze_verified_fields(
        {
            "landlord_name": "임대인",
            "property_address": "가상 주소 1",
            "account_holder": "다른 명의",
            "deposit_return_condition": "명확",
            "repair_responsibility": "명확",
            "rights_change_clause_present": True,
        },
        {
            "owner_names": ["소유자"],
            "property_address": "가상 주소 1",
            "issue_date": "2026-07-01",
            "mortgage_present": False,
            "seizure_present": False,
            "provisional_seizure_present": False,
            "trust_present": False,
        },
        ContractContext(
            contract_id=1,
            contract_type="전세",
            contract_stage="계약금 입금 전",
            deposit_paid=False,
            signed=False,
            is_proxy_contract=False,
        ),
    )
    analysis = AnalysisRunResult(
        analysis_run_id="RUN-J-EVIDENCE",
        input_snapshot_id="SNAP-J-EVIDENCE",
        contract_id=1,
        results=rules,
        judgments=_judgments(),
    )
    allowed_metadata = source_metadata.model_copy(
        update={"source_id": "SRC-STD-LEASE"}
    )
    unrelated_metadata = source_metadata.model_copy(
        update={"source_id": "SRC-HTA-LAW"}
    )
    full_summary = "[특약사항]\n· " + " ".join(
        ["임차인은 전입신고와 확정일자를 확인한다."] * 24
    )
    assert len(full_summary) > 500
    hits = [
        RetrievalHit(
            chunk=chunk_sections(unrelated_metadata, [("제외", "관련 없는 법령")])[0],
            score=2.0,
            rank=1,
            retrieval_method="bm25",
        ),
        RetrievalHit(
            chunk=chunk_sections(allowed_metadata, [("허용", full_summary)])[0],
            score=1.0,
            rank=2,
            retrieval_method="bm25",
        ),
    ]
    service = EvidenceRetrievalService(
        _StaticRetriever(hits),
        judgment_source_ids={"J01": ("SRC-STD-LEASE",)},
    )

    enriched = service.enrich(analysis)

    before = {
        item.judgment_id: item.model_dump(exclude={"evidence_sources"})
        for item in analysis.judgments
    }
    after = {
        item.judgment_id: item.model_dump(exclude={"evidence_sources"})
        for item in enriched.judgments
    }
    assert after == before
    assert [
        source.source_id for source in enriched.judgments[0].evidence_sources
    ] == ["SRC-STD-LEASE"]
    assert enriched.judgments[0].evidence_sources[0].summary == full_summary
    assert all(not item.evidence_sources for item in enriched.judgments[1:])


def test_judgment_source_map_covers_j01_to_j12():
    mapping = load_judgment_source_ids()

    assert list(mapping) == [f"J{index:02d}" for index in range(1, 13)]
    assert mapping["J01"] == ("SRC-STD-LEASE", "SRC-REGISTRY-SAMPLE")


def test_judgment_search_contexts_only_expand_diagnosed_misses():
    contexts = load_judgment_search_contexts()

    assert contexts == {
        "J02": "부동산의 임대차 임차주택 표시 상세주소"
    }


def test_j02_mismatch_retrieves_locally_available_standard_lease_source():
    service = build_evidence_service(load_local_official_chunks())

    result = service.search(
        JudgmentRetrievalQuery(
            judgment_id="J02",
            judgment_name="목적물 주소 일치",
            status="불일치",
            allowed_source_ids=("SRC-STD-LEASE", "SRC-REGISTRY-SAMPLE"),
        )
    )

    assert {hit.chunk.metadata.source_id for hit in result.hits} == {
        "SRC-STD-LEASE"
    }
