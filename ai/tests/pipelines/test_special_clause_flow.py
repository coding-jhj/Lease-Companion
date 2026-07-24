from __future__ import annotations

import json
from pathlib import Path

import pytest

from lease_companion_ai.classification.service import ClassificationService
from lease_companion_ai.generation.models import GeneratedGuidanceDraft, GenerationMethod
from lease_companion_ai.generation.service import GenerationService
from lease_companion_ai.pipelines.classified_analysis import (
    analyze_special_clause_flow,
    analyze_with_classification,
)
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.rag.clause_service import (
    SpecialClauseRetrievalService,
    build_special_clause_retrieval_service,
)
from lease_companion_ai.rag.service import EvidenceSearchResult
from lease_companion_ai.schemas.unified import AnalysisRunResult, InputSnapshot

ROOT = Path(__file__).resolve().parents[3]
FLOW_FIXTURE_PATH = (
    ROOT / "data/sample/fixtures/special-clause-rag-flow/cases.json"
)


def _flow_fixture() -> dict:
    return json.loads(FLOW_FIXTURE_PATH.read_text(encoding="utf-8"))


def _snapshot(*, case_keys: tuple[str, ...] | None = None) -> InputSnapshot:
    fixture = _flow_fixture()
    payload = json.loads(
        (ROOT / fixture["base_input_snapshot"]).read_text(encoding="utf-8")
    )
    selected = [
        case
        for case in fixture["cases"]
        if case_keys is None or case["case_key"] in case_keys
    ]
    contract = payload["confirmed_fields"]["contract"]
    contract["special_clauses"].update(
        extracted_value=[case["text"] for case in selected],
        user_corrected_value=None,
        normalized_value=None,
        confidence="추출됨",
        issue_code=None,
        failure_reason=None,
    )
    contract["special_clauses_present"].update(
        extracted_value=True,
        user_corrected_value=None,
        normalized_value=None,
        confidence="추출됨",
        issue_code=None,
        failure_reason=None,
    )
    return InputSnapshot.model_validate(payload)


class _SelectiveEvidenceService:
    def __init__(self) -> None:
        self._base = build_special_clause_retrieval_service().evidence_service

    def search(self, query, *, top_k=20, top_n=5):
        if "SC-MANAGEMENT-FEE" in query.catalog_ids:
            return EvidenceSearchResult(())
        return self._base.search(query, top_k=top_k, top_n=top_n)


class _GroundedFakeGenerationProvider:
    model_name = "fake-special-clause-flow-v1"

    def __init__(self, *, failing_clause_ids: frozenset[str] = frozenset()) -> None:
        self.failing_clause_ids = failing_clause_ids
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        if request.rule_id in self.failing_clause_ids:
            raise ProviderError("fake special clause generation failure")
        if not request.rule_id.startswith("SC-"):
            raise ProviderError("fake output is only configured for special clauses")
        return GeneratedGuidanceDraft(
            explanation="특약의 조건과 책임 주체를 공식 근거와 함께 확인해 주세요.",
            questions=("특약의 적용 조건과 책임 주체가 구체적으로 적혀 있나요?",),
            request_templates=("적용 조건과 책임 주체를 구체적으로 적어 주세요.",),
            source_ids=(request.evidence[0].source_id,),
        )


def _retrieval_service() -> SpecialClauseRetrievalService:
    return SpecialClauseRetrievalService(_SelectiveEvidenceService())


def test_offline_special_clause_flow_connects_all_stages_from_locked_snapshot():
    snapshot = _snapshot()
    provider = _GroundedFakeGenerationProvider()

    classification, analysis, generation = analyze_special_clause_flow(
        snapshot,
        analysis_run_id="RUN-SPECIAL-FLOW",
        classification_service=ClassificationService(),
        retrieval_service=_retrieval_service(),
        generation_service=GenerationService(provider),
    )

    assert classification.input_snapshot_id == snapshot.input_snapshot_id
    assert len(analysis.results) == 24
    assert len(analysis.judgments) == 13
    reviews = {review.clause_id: review for review in analysis.special_clause_reviews}
    fixture_cases = _flow_fixture()["cases"]
    expected_review_ids = {
        case["expected_clause_id"] for case in fixture_cases if case["expect_review"]
    }
    assert set(reviews) == expected_review_ids
    for case in fixture_cases:
        clause_id = case["expected_clause_id"]
        if not case["expect_review"]:
            assert clause_id not in reviews
            continue
        review = reviews[clause_id]
        assert review.catalog_ids == tuple(case["expected_catalog_ids"])
        assert bool(review.evidence_sources) is case["expect_evidence"]

    guidance = {item.clause_id: item for item in generation.special_clause_items}
    assert set(guidance) == set(reviews)
    assert guidance["SC-0001"].generation_method is GenerationMethod.PROVIDER
    assert guidance["SC-0004"].generation_method is GenerationMethod.PROVIDER
    assert guidance["SC-0005"].generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert guidance["SC-0005"].revision_requests == ()
    assert "공식 근거를 확인하지 못했습니다" in guidance["SC-0005"].plain_explanation
    for clause_id, item in guidance.items():
        allowed = {source.source_id for source in reviews[clause_id].evidence_sources}
        assert set(item.source_ids).issubset(allowed)


def test_rag_provider_failure_preserves_python_analysis_and_uses_no_evidence_fallback():
    snapshot = _snapshot(case_keys=("matched_deferred_refund",))
    _, baseline = analyze_with_classification(
        snapshot,
        analysis_run_id="RUN-RAG-FAILURE",
        classification_service=ClassificationService(),
    )

    class _FailingRetrievalService:
        def enrich(self, _analysis):
            raise ProviderError("fake retrieval provider failure")

    _, analysis, generation = analyze_special_clause_flow(
        snapshot,
        analysis_run_id="RUN-RAG-FAILURE",
        classification_service=ClassificationService(),
        retrieval_service=_FailingRetrievalService(),
        generation_service=GenerationService(),
    )

    assert analysis == baseline
    assert analysis.special_clause_reviews[0].evidence_sources == ()
    item = generation.special_clause_items[0]
    assert item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert item.revision_requests == ()


def test_generation_provider_failure_preserves_enriched_analysis_and_evidence():
    snapshot = _snapshot(case_keys=("matched_deferred_refund",))
    provider = _GroundedFakeGenerationProvider(
        failing_clause_ids=frozenset({"SC-0001"})
    )

    _, analysis, generation = analyze_special_clause_flow(
        snapshot,
        analysis_run_id="RUN-GENERATION-FAILURE",
        classification_service=ClassificationService(),
        retrieval_service=build_special_clause_retrieval_service(),
        generation_service=GenerationService(provider),
    )

    review = analysis.special_clause_reviews[0]
    assert review.evidence_sources
    item = generation.special_clause_items[0]
    assert item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert item.source_ids == tuple(
        source.source_id for source in review.evidence_sources
    )
    linked = next(
        judgment
        for judgment in analysis.judgments
        if judgment.judgment_id == review.related_judgment_ids[0]
    )
    assert review.status is linked.status
    assert review.urgency is linked.urgency


def test_pipeline_rejects_retrieval_that_mutates_python_results():
    snapshot = _snapshot(case_keys=("matched_deferred_refund",))

    class _MutatingRetrievalService:
        def enrich(self, analysis: AnalysisRunResult) -> AnalysisRunResult:
            changed = analysis.results[0].model_copy(update={"reason": "변경됨"})
            return analysis.model_copy(update={"results": [changed, *analysis.results[1:]]})

    with pytest.raises(RuntimeError, match="판정"):
        analyze_special_clause_flow(
            snapshot,
            analysis_run_id="RUN-MUTATION",
            classification_service=ClassificationService(),
            retrieval_service=_MutatingRetrievalService(),
            generation_service=GenerationService(),
        )
