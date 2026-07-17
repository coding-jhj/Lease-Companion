from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# 도메인 엔터티 매핑: checklist = ChecklistItem(서명 전) / post_action = PostContractAction(계약 직후)
KIND_CHECKLIST = "checklist"
KIND_POST_ACTION = "post_action"


class ChecklistItemState(Base):
    """체크리스트·계약 직후 행동 항목의 사용자 확인 상태 (계약 건 단위 저장·재조회).

    항목 내용(문구·근거)은 분석 결과·A 3단계 생성 산출물이 원본이므로 저장하지 않는다 —
    여기는 (contract_id, kind, item_key)별 done 상태만 남긴다.
    ponytail: item_key는 클라이언트가 보내는 안정 식별자(예: rule_id) — A의 생성 스키마
    확정 후 항목 존재 검증을 붙일 수 있다.
    """

    __tablename__ = "checklist_item_states"
    __table_args__ = (UniqueConstraint("contract_id", "kind", "item_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract_projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    item_key: Mapped[str] = mapped_column(String(100))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
