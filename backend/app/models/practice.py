"""계약 연습 세션·턴 영속 모델.

실제 계약 건과 합성 연습 데이터를 분리하며, canonical simulation JSON은
재구성하지 않고 검증된 payload 그대로 저장한다.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

_JSON = JSON().with_variant(JSONB(), "postgresql")


class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    practice_session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(String(80), index=True)
    scenario_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), index=True)
    current_state: Mapped[str] = mapped_column(String(40))
    current_turn_id: Mapped[str | None] = mapped_column(String(40))
    confirmed_action_ids: Mapped[list[str]] = mapped_column(_JSON, default=list)
    selected_action: Mapped[str | None] = mapped_column(String(30))
    state_payload: Mapped[dict] = mapped_column(_JSON)
    result: Mapped[dict | None] = mapped_column(_JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PracticeTurn(Base):
    __tablename__ = "practice_turns"
    __table_args__ = (
        UniqueConstraint("practice_session_fk", "request_id", name="uq_practice_turn_session_request"),
        Index(
            "ix_practice_turn_session_turn_attempt",
            "practice_session_fk",
            "turn_id",
            "attempt_no",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    practice_turn_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    practice_session_fk: Mapped[int] = mapped_column(ForeignKey("practice_sessions.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(40))
    attempt_no: Mapped[int] = mapped_column(Integer)
    request_id: Mapped[str] = mapped_column(String(64))
    input_payload: Mapped[dict] = mapped_column(_JSON)
    evaluation_payload: Mapped[dict | None] = mapped_column(_JSON)
    dialogue_response: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
