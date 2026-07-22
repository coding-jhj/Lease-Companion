from __future__ import annotations

import json
from pathlib import Path

import pytest

from lease_companion_ai.providers.rerank import RerankResult
from lease_companion_ai.rag.clause_service import (
    SpecialClauseRetrievalService,
    build_clause_retrieval_query,
    build_special_clause_retrieval_service,
)
from lease_companion_ai.rag.indexing.chunker import extract_named_section
from lease_companion_ai.rag.models import ClauseRetrievalQuery, SourceSectionFilter
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    SpecialClauseReview,
)
from lease_companion_ai.special_clauses import match_special_clauses


ROOT = Path(__file__).resolve().parents[3]
LOCKED_RETRIEVAL_CASES = tuple(
    json.loads(line)
    for line in (
        ROOT / "data/evaluation/special-clauses/retrieval_test.jsonl"
    ).read_text(encoding="utf-8").splitlines()
)


class _LockedFixtureReranker:
    model_name = "fake-special-clause-rerank-v1"

    _expected_sections = {
        case["target_catalog_id"]: tuple(case["expected_sections"])
        for case in LOCKED_RETRIEVAL_CASES
        if case["target_catalog_id"] is not None
        and case["target_catalog_id"] != "SC-MAIN-SPECIAL-CONFLICT"
    }

    def rerank(self, query, documents, *, top_n):
        catalog_id = next(
            catalog_id for catalog_id in self._expected_sections if catalog_id in query
        ) if "SC-MAIN-SPECIAL-CONFLICT" not in query else "SC-MAIN-SPECIAL-CONFLICT"
        expected = (
            ("제9조(계약의 종료)", "제536조(동시이행의 항변권)")
            if catalog_id == "SC-MAIN-SPECIAL-CONFLICT" and "보증금" in query
            else self._expected_sections[catalog_id]
        )
        results = []
        for score, section in enumerate(expected, start=1):
            index = next(index for index, document in enumerate(documents) if section in document)
            results.append(RerankResult(index=index, score=1.0 / score))
        return results


def test_clause_query_contains_catalog_result_and_deidentified_original_text():
    query = ClauseRetrievalQuery(
        clause_id="SC-0001",
        catalog_ids=("SC-DEFERRED-REFUND",),
        catalog_names=("보증금 반환을 미래 사건에 연동한 조건",),
        related_result_contexts=("J10 보증금 반환 시점·조건 명확성 확인 필요",),
        status="확인 필요",
        allowed_source_sections=(
            SourceSectionFilter(
                source_id="SRC-STD-LEASE",
                article_or_section="제9조(계약의 종료)",
            ),
        ),
        deidentified_clause_context="[PERSON_1]에게 보증금을 반환한다.",
    )

    assert query.allowed_source_ids == ("SRC-STD-LEASE",)
    assert query.allowed_section_pairs == (
        ("SRC-STD-LEASE", "제9조(계약의 종료)"),
    )
    assert query.to_search_text() == (
        "SC-DEFERRED-REFUND 보증금 반환을 미래 사건에 연동한 조건 "
        "J10 보증금 반환 시점·조건 명확성 확인 필요 확인 필요 "
        "[PERSON_1]에게 보증금을 반환한다."
    )


@pytest.mark.parametrize(
    ("source", "section", "needle"),
    [
        ("SRC-CIVIL-LEASE.txt", "제536조(동시이행의 항변권)", "쌍무계약"),
        ("SRC-CIVIL-LEASE.txt", "제615조·제654조(원상회복 준용)", "준용규정"),
        ("SRC-STD-LEASE.txt", "제4조 제2항~제4항(임차주택의 사용·관리·수선)", "수선비용"),
        ("SRC-HTA-LAW.txt", "제4조 제2항(보증금 반환 전 임대차관계 존속)", "보증금을 반환"),
        ("SRC-STD-LEASE.txt", "[특약사항] 담보권 설정 금지·위반 시 해제 또는 해지", "담보권"),
        ("SRC-MOLIT-CHECKLIST.txt", "잔금 지급 전 권리관계 재확인", "다시 발급"),
    ],
)
def test_extract_named_section_preserves_catalog_section(source, section, needle):
    text = (ROOT / "data/rag/sources" / source).read_text(encoding="utf-8")

    extracted = extract_named_section(text, section)

    assert needle in extracted


@pytest.mark.parametrize(
    "case",
    LOCKED_RETRIEVAL_CASES,
    ids=[case["case_id"] for case in LOCKED_RETRIEVAL_CASES],
)
def test_locked_clause_retrieval_stays_inside_source_and_section_allowlist(case):
    candidates = match_special_clauses([case["text"]])
    candidate = candidates[0]
    if not case["expect_evidence"]:
        assert candidate.catalog_ids == ()
        return

    service = build_special_clause_retrieval_service(
        rerank_provider=_LockedFixtureReranker()
    )
    query = build_clause_retrieval_query(
        candidate,
        status="확인 필요",
        related_result_contexts=tuple(
            [*candidate.related_rule_ids, *candidate.related_judgment_ids]
        ),
    )

    result = service.search(query)
    actual_pairs = [
        (hit.chunk.metadata.source_id, hit.chunk.section) for hit in result.hits
    ]
    expected_pairs = list(
        zip(case["expected_source_ids"], case["expected_sections"], strict=True)
    )
    assert actual_pairs == expected_pairs
    assert set(actual_pairs) <= set(query.allowed_section_pairs)
    assert len(actual_pairs) <= 3


def test_special_clause_enrichment_changes_only_card_evidence_and_removes_raw_pii():
    fixture = ROOT / "data/sample/fixtures/case-001/analysis_run_result.json"
    analysis = AnalysisRunResult.model_validate_json(fixture.read_text(encoding="utf-8"))
    r19 = next(result for result in analysis.results if result.rule_id == "R19")
    review = SpecialClauseReview(
        clause_id="SC-0001",
        original_text="임대인 홍길동 010-1234-5678은 근저당을 자유롭게 설정한다.",
        catalog_ids=("SC-RIGHTS-CHANGE",),
        match_method="catalog_pattern",
        related_rule_ids=("R10", "R19"),
        status=r19.status,
        urgency=r19.urgency,
        reason=r19.reason,
        triggers_actions=r19.triggers_actions,
        limitations=r19.limitations,
    )
    analysis = analysis.model_copy(update={"special_clause_reviews": [review]})
    captured: list[ClauseRetrievalQuery] = []
    base = build_special_clause_retrieval_service()

    class _CapturingEvidenceService:
        def search(self, query, *, top_k=20, top_n=5):
            captured.append(query)
            return base.evidence_service.search(query, top_k=top_k, top_n=top_n)

    service = SpecialClauseRetrievalService(_CapturingEvidenceService())
    enriched = service.enrich(analysis)

    assert captured
    assert "홍길동" not in captured[0].deidentified_clause_context
    assert "010-1234-5678" not in captured[0].deidentified_clause_context
    assert analysis.model_dump(exclude={"special_clause_reviews"}) == enriched.model_dump(
        exclude={"special_clause_reviews"}
    )
    before = review.model_dump(exclude={"evidence_sources"})
    after = enriched.special_clause_reviews[0].model_dump(exclude={"evidence_sources"})
    assert before == after
    assert enriched.special_clause_reviews[0].evidence_sources
    assert all(
        source.article_or_section is not None
        for source in enriched.special_clause_reviews[0].evidence_sources
    )


def test_empty_retrieval_preserves_card_and_returns_empty_evidence():
    class _EmptyEvidenceService:
        def search(self, _query, *, top_k=20, top_n=5):
            from lease_companion_ai.rag.service import EvidenceSearchResult

            return EvidenceSearchResult(())

    fixture = ROOT / "data/sample/fixtures/case-001/analysis_run_result.json"
    analysis = AnalysisRunResult.model_validate_json(fixture.read_text(encoding="utf-8"))
    r19 = next(result for result in analysis.results if result.rule_id == "R19")
    review = SpecialClauseReview(
        clause_id="SC-0001",
        original_text="임대인은 근저당을 자유롭게 설정한다.",
        catalog_ids=("SC-RIGHTS-CHANGE",),
        match_method="catalog_pattern",
        related_rule_ids=("R10", "R19"),
        status=r19.status,
        urgency=r19.urgency,
        reason=r19.reason,
        triggers_actions=r19.triggers_actions,
        limitations=r19.limitations,
    )
    analysis = analysis.model_copy(update={"special_clause_reviews": [review]})

    enriched = SpecialClauseRetrievalService(_EmptyEvidenceService()).enrich(analysis)

    assert enriched.special_clause_reviews[0] == review


def test_same_j10_context_uses_original_clause_to_change_bm25_section_order():
    service = build_special_clause_retrieval_service()
    first_sections = []
    for text in (
        "보증금은 신규 임차인이 입주한 뒤 반환한다.",
        "주택을 매각한 뒤 보증금을 반환한다.",
    ):
        candidate = match_special_clauses([text])[0]
        query = build_clause_retrieval_query(
            candidate,
            status="확인 필요",
            related_result_contexts=("J10 보증금 반환 조건 확인 필요",),
        )
        result = service.search(query)
        assert result.hits
        first_sections.append(result.hits[0].chunk.section)

    assert first_sections[0] != first_sections[1]
