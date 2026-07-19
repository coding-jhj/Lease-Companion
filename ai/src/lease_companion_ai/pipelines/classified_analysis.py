"""사용자 확인 snapshot의 classification과 규칙 분석을 연결하는 AI 전용 경계."""

from __future__ import annotations

from lease_companion_ai.classification.service import ClassificationService
from lease_companion_ai.schemas.adapters import analyze_snapshot
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    ClassificationResult,
    InputSnapshot,
)


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
    return classification_result, analysis_result
