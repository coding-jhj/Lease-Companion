from __future__ import annotations

import json
from pathlib import Path

from lease_companion_ai.classification.service import ClassificationService
from lease_companion_ai.pipelines.classified_analysis import (
    analyze_with_classification,
)
from lease_companion_ai.providers.classification import (
    CLASSIFICATION_PROMPT_VERSION,
    FakeClassificationProvider,
)
from lease_companion_ai.schemas.unified import (
    ClassificationMethod,
    ClassificationResult,
    ClauseCandidate,
    InputSnapshot,
    RuleStatus,
)
from lease_companion_ai.generation.service import GenerationService
from lease_companion_ai.providers.generation import FakeGenerationProvider
from lease_companion_ai.rag.service import EvidenceRetrievalService

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "data" / "sample" / "fixtures" / "case-001" / "input_snapshot.json"


def _snapshot() -> InputSnapshot:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["schema_version"] = "1.9.0"
    payload["contract_context"]["schema_version"] = "1.9.0"
    contract = payload["confirmed_fields"]["contract"]
    contract["deposit_return_clause"].update(
        extracted_value="임대인은 계약 종료일에 보증금을 반환한다.",
        confidence="추출됨",
        issue_code=None,
        failure_reason=None,
    )
    return InputSnapshot.model_validate(payload)


def _provider_result(snapshot: InputSnapshot) -> ClassificationResult:
    return ClassificationResult(
        schema_version=snapshot.schema_version,
        input_snapshot_id=snapshot.input_snapshot_id,
        contract_id=snapshot.contract_id,
        provider_model="fake-classification-v1",
        prompt_version=CLASSIFICATION_PROMPT_VERSION,
        classification_method=ClassificationMethod.PROVIDER,
        candidates=[
            ClauseCandidate(
                clause_ref="deposit_return_clause:0",
                clause_type="deposit_return",
                clarity_candidate="명확",
                responsible_party_candidate="임대인",
                condition_candidates=["계약 종료일"],
                review_required=False,
            )
        ],
    )


def _status(analysis, judgment_id: str) -> RuleStatus:
    return next(
        result.status for result in analysis.judgments if result.judgment_id == judgment_id
    )


def _snapshot_with_unreadable_special_clauses() -> InputSnapshot:
    """special_clauses가 PARSE_FAILED인 스냅샷 — J13이 확인 불가로 triggers_actions=True가 된다."""
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["schema_version"] = "1.9.0"
    payload["contract_context"]["schema_version"] = "1.9.0"
    contract = payload["confirmed_fields"]["contract"]
    contract["deposit_return_clause"].update(
        extracted_value="임대인은 계약 종료일에 보증금을 반환한다.",
        confidence="추출됨",
        issue_code=None,
        failure_reason=None,
    )
    contract["special_clauses"].update(
        extracted_value=None,
        normalized_value=None,
        user_corrected_value=None,
        confidence="실패",
        issue_code="parse_failed",
        failure_reason="특약 원문을 판독하지 못했습니다.",
    )
    return InputSnapshot.model_validate(payload)


def test_provider_candidates_are_passed_to_judgment_analysis() -> None:
    snapshot = _snapshot()
    expected = _provider_result(snapshot)
    provider = FakeClassificationProvider({snapshot.input_snapshot_id: expected})

    classification, analysis = analyze_with_classification(
        snapshot,
        analysis_run_id="RUN-CLASSIFIED",
        classification_service=ClassificationService(provider),
    )

    assert classification == expected
    assert _status(analysis, "J10") is RuleStatus.CLEAR
    assert analysis.input_snapshot_id == classification.input_snapshot_id
    assert analysis.contract_id == classification.contract_id


class _EmptyRetriever:
    """검색 결과가 없어도 J13처럼 새 판정 id가 pydantic pattern에서 거부되면 크래시가 재현돼야 한다."""

    def search(self, _query, *, top_k=20):
        return []


def test_unreadable_special_clauses_flow_through_rag_and_generation_without_crash() -> None:
    """J13 확인 불가(=judgment_id 패턴이 J01~J12만 허용하던 시절엔 크래시)가
    분석 → RAG 판정 근거 보강 → 생성 전체 경로에서 예외 없이 끝까지 흘러야 한다.
    유닛 테스트로 `_j13`만 부르는 것으로는 이 경로의 크래시를 잡아내지 못한다.
    """
    snapshot = _snapshot_with_unreadable_special_clauses()

    classification, analysis = analyze_with_classification(
        snapshot,
        analysis_run_id="RUN-J13-UNREADABLE",
        classification_service=ClassificationService(),
    )

    j13 = next(result for result in analysis.judgments if result.judgment_id == "J13")
    assert j13.status is RuleStatus.CANNOT_CHECK
    assert j13.triggers_actions is True

    enriched = EvidenceRetrievalService(_EmptyRetriever()).enrich(analysis)
    enriched_j13 = next(
        result for result in enriched.judgments if result.judgment_id == "J13"
    )
    assert enriched_j13.status is RuleStatus.CANNOT_CHECK

    generated = GenerationService(FakeGenerationProvider({})).generate(
        enriched, snapshot.contract_context
    )
    guidance_ids = {item.judgment_id for item in generated.judgment_items}
    assert "J13" in guidance_ids


def test_safe_fallback_keeps_analysis_available_without_candidates() -> None:
    snapshot = _snapshot()

    classification, analysis = analyze_with_classification(
        snapshot,
        analysis_run_id="RUN-FALLBACK",
        classification_service=ClassificationService(),
    )

    assert classification.classification_method is ClassificationMethod.SAFE_FALLBACK
    assert classification.candidates == []
    assert _status(analysis, "J10") is RuleStatus.CHECK_NEEDED
    assert [result.rule_id for result in analysis.results] == [
        f"R{index:02d}" for index in range(1, 25)
    ]


def _snapshot_with_special_clauses(*texts: str) -> InputSnapshot:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["schema_version"] = "1.9.0"
    payload["contract_context"]["schema_version"] = "1.9.0"
    contract = payload["confirmed_fields"]["contract"]
    contract["special_clauses"].update(
        extracted_value=list(texts),
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


def _analyze(snapshot: InputSnapshot):
    provider = FakeClassificationProvider({})
    _, analysis = analyze_with_classification(
        snapshot,
        analysis_run_id="RUN-SC",
        classification_service=ClassificationService(provider),
    )
    return analysis


def test_matched_special_clause_becomes_review_linked_to_rule_engine_result():
    snapshot = _snapshot_with_special_clauses(
        "임대인은 새로운 임차인의 입주가 완료된 이후에 보증금을 반환한다."
    )
    analysis = _analyze(snapshot)

    # R/J 결과는 그대로 (24 규칙·13 판정 — J13 포함)
    assert len(analysis.results) == 24
    assert len(analysis.judgments) == 13

    assert len(analysis.special_clause_reviews) == 1
    review = analysis.special_clause_reviews[0]
    assert review.catalog_ids == ("SC-DEFERRED-REFUND",)
    assert review.match_method == "catalog_pattern"
    assert "J10" in review.related_judgment_ids
    # 상태·시급도는 규칙 엔진 결과를 그대로 반영한다 (카탈로그가 만들지 않음)
    j10 = next(j for j in analysis.judgments if j.judgment_id == "J10")
    assert review.status is j10.status
    assert review.urgency is j10.urgency
    # 근거는 Task 4(특약 RAG)에서 연결 — 지금은 비어 있음
    assert review.evidence_sources == ()


def test_protective_special_clause_is_unmatched_and_makes_no_review():
    snapshot = _snapshot_with_special_clauses(
        "임대인은 잔금 지급 전까지 새로운 권리변동을 발생시키지 않는다."
    )
    analysis = _analyze(snapshot)
    assert analysis.special_clause_reviews == []
