from __future__ import annotations

from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.rag.models import RetrievalHit
from lease_companion_ai.rag.service import EvidenceRetrievalService
from lease_companion_ai.schemas.unified import AnalysisRunResult, ContractContext


class _StaticRetriever:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits

    def search(self, _query, *, top_k=20):
        return self.hits[:top_k]


class _FailedRetriever:
    def search(self, _query, *, top_k=20):
        raise ProviderError("provider unavailable")


def test_enrichment_preserves_rule_fields_and_adds_only_searched_official_sources():
    from lease_companion_ai.rag.service import get_local_evidence_service
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
    enriched = get_local_evidence_service().enrich(
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
