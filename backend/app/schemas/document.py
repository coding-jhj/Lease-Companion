from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# 업로드 문서 3종 (user-flow 4단계: 계약서·특약 필수 / 나머지 선택)
DocType = Literal["계약서", "등기사항증명서", "중개대상물 확인설명서"]


class DocumentResponse(BaseModel):
    id: int
    doc_type: str
    filename: str
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RegistryLinkRequest(BaseModel):
    """모의 등기 연결 — data/sample/registry-records의 합성 사례 식별자."""

    case_id: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
