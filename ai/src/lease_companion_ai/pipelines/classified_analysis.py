"""사용자 확인 snapshot의 classification과 규칙 분석을 연결하는 AI 전용 경계."""

from __future__ import annotations

import logging
from typing import Protocol

from lease_companion_ai.classification.service import ClassificationService
from lease_companion_ai.generation.service import GenerationService
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.rag.clause_service import (
    build_special_clause_retrieval_service,
)
from lease_companion_ai.schemas.adapters import analyze_snapshot
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    ClassificationResult,
    GenerationResult,
    InputSnapshot,
    JudgmentResult,
    RuleResult,
    SpecialClauseReview,
)
from lease_companion_ai.special_clauses import SpecialClauseCandidate, match_special_clauses

logger = logging.getLogger(__name__)


class SpecialClauseAnalysisEnricher(Protocol):
    def enrich(self, analysis: AnalysisRunResult) -> AnalysisRunResult: ...


def _confirmed_special_clauses(snapshot: InputSnapshot) -> list[str]:
    field = snapshot.confirmed_fields.contract.get("special_clauses")
    value = field.effective_value if field is not None else None
    if not isinstance(value, (list, tuple)):
        return []
    return [clause for clause in value if isinstance(clause, str) and clause.strip()]


def _build_special_clause_reviews(
    analysis: AnalysisRunResult, candidates: tuple[SpecialClauseCandidate, ...]
) -> list[SpecialClauseReview]:
    """매칭 후보를 이미 확정된 R/J 결과에 연결한다.

    status·urgency·reason은 규칙 엔진이 정한 연결 결과를 그대로 반영하고,
    카탈로그·매칭은 이를 만들거나 바꾸지 않는다. 근거는 Task 4(특약 RAG)에서 연결한다.
    미매칭 후보나 분석에 없는 R/J만 가진 후보는 카드로 만들지 않는다.
    """
    rule_by_id = {result.rule_id: result for result in analysis.results}
    judgment_by_id = {result.judgment_id: result for result in analysis.judgments}
    reviews: list[SpecialClauseReview] = []
    for candidate in candidates:
        related_judgments = tuple(
            jid for jid in candidate.related_judgment_ids if jid in judgment_by_id
        )
        related_rules = tuple(rid for rid in candidate.related_rule_ids if rid in rule_by_id)
        # 상태·시급도의 출처: 판정(J) 우선, 없으면 규칙(R).
        source: JudgmentResult | RuleResult | None = None
        if related_judgments:
            source = judgment_by_id[related_judgments[0]]
        elif related_rules:
            source = rule_by_id[related_rules[0]]
        if source is None:
            continue
        reviews.append(
            SpecialClauseReview(
                clause_id=candidate.clause_id,
                original_text=candidate.original_text,
                catalog_ids=candidate.catalog_ids,
                match_method=candidate.match_method,
                related_rule_ids=related_rules,
                related_judgment_ids=related_judgments,
                status=source.status,
                urgency=source.urgency,
                reason=source.reason,
                triggers_actions=source.triggers_actions,
                evidence_sources=(),
                limitations=source.limitations,
            )
        )
    return reviews


def attach_special_clause_reviews(
    snapshot: InputSnapshot, analysis: AnalysisRunResult
) -> AnalysisRunResult:
    """확인 특약을 카탈로그로 매칭해 clause linkage metadata를 분석 결과에 붙인다.

    규칙 엔진 결과(status/urgency/reason)는 변경하지 않는다.
    """
    clauses = _confirmed_special_clauses(snapshot)
    candidates = match_special_clauses(clauses)
    matched = [candidate for candidate in candidates if candidate.catalog_ids]
    reviews = _build_special_clause_reviews(analysis, candidates)
    # 카드 0건은 "실패"와 "위험 특약 없음"이 전혀 다른데 지금까지 구분되지 않았다.
    # 세 숫자를 함께 남겨 어느 단계에서 걸러졌는지 로그만으로 알 수 있게 한다.
    logger.info(
        "특약 매칭 확인특약=%d 카탈로그매칭=%d 카드=%d",
        len(clauses),
        len(matched),
        len(reviews),
    )
    if clauses and not matched:
        logger.info(
            "특약 %d건이 위험 특약 카탈로그(%s)에 해당하지 않습니다 — 정상 결과입니다.",
            len(clauses),
            "확인 특약 카탈로그 11종",
        )
    if not reviews:
        return analysis
    return analysis.model_copy(update={"special_clause_reviews": reviews})


def analyze_with_classification(
    snapshot: InputSnapshot,
    *,
    analysis_run_id: str,
    classification_service: ClassificationService,
) -> tuple[ClassificationResult, AnalysisRunResult]:
    """Classification 후보를 만든 뒤 동일 snapshot의 규칙 분석에 전달한다.

    저장·상태 전이·재시도는 Backend 책임이다. 이 함수는 canonical 입력과 결과만
    연결하며 ClassificationService의 safe fallback도 일반 결과처럼 규칙에 전달한다.
    """

    classification_result = classification_service.classify(snapshot)
    analysis_result = analyze_snapshot(
        snapshot,
        analysis_run_id=analysis_run_id,
        classification_result=classification_result,
    )
    analysis_result = attach_special_clause_reviews(snapshot, analysis_result)
    return classification_result, analysis_result


def _enforce_retrieval_immutability(
    before: AnalysisRunResult, after: AnalysisRunResult
) -> None:
    """RAG가 공식 근거 외 분석 필드를 바꾸면 전체 흐름을 중단한다."""

    if before.model_dump(exclude={"special_clause_reviews"}) != after.model_dump(
        exclude={"special_clause_reviews"}
    ):
        raise RuntimeError("특약 RAG가 Python 판정 결과를 변경했습니다.")
    before_reviews = {review.clause_id: review for review in before.special_clause_reviews}
    after_reviews = {review.clause_id: review for review in after.special_clause_reviews}
    if before_reviews.keys() != after_reviews.keys():
        raise RuntimeError("특약 RAG가 특약 판정 대상을 변경했습니다.")
    for clause_id, before_review in before_reviews.items():
        if before_review.model_dump(exclude={"evidence_sources"}) != after_reviews[
            clause_id
        ].model_dump(exclude={"evidence_sources"}):
            raise RuntimeError("특약 RAG가 특약 판정 필드를 변경했습니다.")


def analyze_special_clause_flow(
    snapshot: InputSnapshot,
    *,
    analysis_run_id: str,
    classification_service: ClassificationService,
    retrieval_service: SpecialClauseAnalysisEnricher | None = None,
    generation_service: GenerationService | None = None,
) -> tuple[ClassificationResult, AnalysisRunResult, GenerationResult]:
    """확인 snapshot부터 특약 근거·안내까지 AI 전용 종단 흐름을 실행한다.

    저장과 실행 상태 전이는 Backend 책임이다. 외부 검색 provider 실패는 근거 없는
    카드로 흡수하지만, schema 오류와 R/J·특약 판정 변경은 숨기지 않는다.
    """

    classification, enriched = analyze_special_clause_evidence(
        snapshot,
        analysis_run_id=analysis_run_id,
        classification_service=classification_service,
        retrieval_service=retrieval_service,
    )
    generator = generation_service or GenerationService()
    generation = generator.generate(enriched, snapshot.contract_context)
    return classification, enriched, generation


def analyze_special_clause_evidence(
    snapshot: InputSnapshot,
    *,
    analysis_run_id: str,
    classification_service: ClassificationService,
    retrieval_service: SpecialClauseAnalysisEnricher | None = None,
) -> tuple[ClassificationResult, AnalysisRunResult]:
    """Python 판정과 특약 공식 근거까지 실행해 생성 전 저장 경계를 만든다."""

    classification, analysis = analyze_with_classification(
        snapshot,
        analysis_run_id=analysis_run_id,
        classification_service=classification_service,
    )
    enricher: SpecialClauseAnalysisEnricher = (
        retrieval_service or build_special_clause_retrieval_service()
    )
    try:
        enriched = enricher.enrich(analysis)
    except ProviderError:
        logger.warning(
            "special_clause_retrieval_provider_failed",
            extra={"analysis_run_id": analysis_run_id},
        )
        enriched = analysis
    _enforce_retrieval_immutability(analysis, enriched)
    return classification, enriched
