"""추출·분석 API 요청·응답 wrapper.

도메인 본문(DocumentExtraction/InputSnapshot/AnalysisRunResult)은 통합 스키마가
단일 원본 — 여기서는 실행 상태·목록 요약만 정의하고 본문은 canonical JSON 그대로 반환.
status: pending → running → completed | failed (폴링 — 2026-07-16 팀 확정).
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ExtractionState(BaseModel):
    """추출 실행 상태 + (완료 시) 수정 이력 반영된 현재 추출값."""

    id: int
    status: str
    error: str | None = None
    contract_doc: dict[str, Any] | None = None
    registry_doc: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SnapshotResponse(BaseModel):
    """확인 완료로 생성된 불변 스냅샷 — snapshot에 canonical InputSnapshot JSON 전체 포함
    (2026-07-17 A 권장안: contract_context 포함 여부를 클라이언트가 바로 확인 가능)."""

    input_snapshot_id: str
    created_at: datetime
    snapshot: dict[str, Any]

    model_config = {"from_attributes": True}


class AnalysisRunSummary(BaseModel):
    """재분석 이력 목록 항목."""

    analysis_run_id: str
    input_snapshot_id: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisRunDetail(BaseModel):
    """분석 실행 1회 — result는 completed 후 통합 AnalysisRunResult JSON, 그 전엔 null.

    generation_result는 규칙 판정과 분리된 생성 결과(GenerationResult JSON, 2026-07-17 합의).
    생성 시작 전·guardrail 미통과·생성 실패 시 null — 규칙 result에는 영향 없음.
    """

    analysis_run_id: str
    input_snapshot_id: str
    status: str
    error: str | None = None
    created_at: datetime
    result: dict[str, Any] | None = None
    generation_result: dict[str, Any] | None = None
    generation_status: str | None = None
    generation_error: str | None = None

    model_config = {"from_attributes": True}
