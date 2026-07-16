from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ContractProject(Base):
    """계약 건. 분석·문서·체크리스트가 모두 이 단위(contract_id)에 매달린다."""

    __tablename__ = "contract_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    # 계약 상황 입력(사용자 흐름 3단계)에서 채워짐 — 생성 시점에는 비어 있음
    contract_type: Mapped[str | None] = mapped_column(String(20))  # 전세/보증부 월세/일반 월세
    contract_stage: Mapped[str | None] = mapped_column(String(50))  # TODO: 단계 값 목록 팀 확정 전 자유 문자열
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
