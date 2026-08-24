from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, Field

# 분석 입력 문서 3종 (user-flow 4단계: 계약서·특약 필수 / 나머지 선택)
AnalysisDocType = Literal["계약서", "등기사항증명서", "중개대상물 확인설명서"]
# 증빙 보관 4종. 분석 입력이 아니라 분쟁 대비 보관물이라 추출·판정에 쓰지 않는다.
EvidenceDocType = Literal["이체내역", "대화기록", "현장사진", "기타 증빙"]

DocType = Literal[AnalysisDocType, EvidenceDocType]

EVIDENCE_DOC_TYPES: frozenset[str] = frozenset(get_args(EvidenceDocType))


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
