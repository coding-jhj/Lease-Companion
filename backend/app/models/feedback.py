from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserFeedback(Base):
    """사용자 피드백 (계약 건 단위 이력 — 수정·삭제 없이 쌓기만 한다).

    자유 텍스트 + 선택 평점 최소형. 판정 항목별 피드백 등 세분화는
    화면 요구가 생기면 필드 추가로 확장(canonical 스키마와 무관한 backend 전용 엔터티).
    """

    __tablename__ = "user_feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract_projects.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(String(2000))
    rating: Mapped[int | None] = mapped_column(Integer)  # 1~5, 선택
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
