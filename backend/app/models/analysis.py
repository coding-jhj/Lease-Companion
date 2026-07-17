from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# 운영 PostgreSQL은 JSONB, 테스트 sqlite는 JSON
_JSON = JSON().with_variant(JSONB(), "postgresql")

# 비동기 실행 상태 (폴링 — 2026-07-16 팀 확정). 화면 표시 문구는 frontend 몫
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class ExtractionRun(Base):
    """추출 실행 1회 (비동기). contract_doc/registry_doc은 통합 DocumentExtraction JSON —
    수정 전 원본으로 보존하며 이후 절대 갱신하지 않는다(수정은 CorrectionRecord 재생으로 계산).
    """

    __tablename__ = "extraction_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract_projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING)
    error: Mapped[str | None] = mapped_column(Text)
    contract_doc: Mapped[dict | None] = mapped_column(_JSON)
    registry_doc: Mapped[dict | None] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CorrectionRecord(Base):
    """사용자 수정 요청 이력 — 통합 CorrectionRequest JSON을 그대로 보존한다.
    현재 추출 상태 = 원본 ExtractionRun + 이 이력의 순서대로 재적용(재생)."""

    __tablename__ = "correction_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract_projects.id"), index=True)
    extraction_run_id: Mapped[int] = mapped_column(ForeignKey("extraction_runs.id"))
    payload: Mapped[dict] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InputSnapshotRecord(Base):
    """사용자 확인 완료 입력의 불변 사본 — 통합 InputSnapshot JSON."""

    __tablename__ = "input_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract_projects.id"), index=True)
    input_snapshot_id: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AnalysisRun(Base):
    """분석 실행 1회 (비동기 — 폴링으로 상태 조회). 재분석마다 새 행 = 이력·버전 축.

    input_snapshot / result 는 통합 스키마(InputSnapshot / AnalysisRunResult)의
    JSON 그대로 저장한다 (canonical 모델이 검증 담당 — 컬럼 분해는 조회 요구 생기면).
    result는 completed 전까지 null.
    """

    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract_projects.id"), index=True)
    analysis_run_id: Mapped[str] = mapped_column(String(64), unique=True)
    input_snapshot_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING)
    error: Mapped[str | None] = mapped_column(Text)
    input_snapshot: Mapped[dict] = mapped_column(_JSON)
    result: Mapped[dict | None] = mapped_column(_JSON)
    # 생성 결과 (2026-07-17 3인 합의): 규칙 판정(result)과 분리 저장, 같은 analysis_run_id로 연결.
    # guardrail_passed=true인 GenerationResult JSON만 저장한다.
    # 생성 실패는 규칙 결과에 전파하지 않는다 — 상태·오류를 별도 필드로 남긴다(status는 분석과 별개).
    generation_result: Mapped[dict | None] = mapped_column(_JSON)
    generation_status: Mapped[str | None] = mapped_column(String(20))
    generation_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
