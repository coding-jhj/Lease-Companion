from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Document(Base):
    """업로드 문서. 같은 계약 건에 같은 종류를 다시 올리면 새 행이 쌓인다(이력)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract_projects.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(30))  # 계약서/등기사항증명서/중개대상물 확인설명서
    filename: Mapped[str] = mapped_column(String(255))  # 사용자가 올린 원본 파일명
    stored_path: Mapped[str] = mapped_column(String(500))  # 서버 저장 경로 (uuid 파일명)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
