"""사용자 확인 snapshot의 classification과 규칙 분석을 연결하는 AI 전용 경계."""

from __future__ import annotations

from lease_companion_ai.classification.service import ClassificationService
from lease_companion_ai.schemas.adapters import analyze_snapshot
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    ClassificationResult,
    InputSnapshot,
    SpecialClauseReview,
)
from lease_companion_ai.special_clauses import SpecialClauseCandidate, match_special_clauses


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
        source = None
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
    candidates = match_special_clauses(_confirmed_special_clauses(snapshot))
    reviews = _build_special_clause_reviews(analysis, candidates)
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
