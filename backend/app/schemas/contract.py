from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# 대상 계약 3종 (루트 AGENTS.md 확정)
ContractType = Literal["전세", "보증부 월세", "일반 월세"]

# 계약 단계 3개 (2026-07-16 팀 확정). '계약 직후' 단계는 전입신고 근거·미신고 리스크
# 사례를 함께 제공하기로 함 — 해당 콘텐츠 생성은 담당 A(RAG·생성) 영역
ContractStage = Literal["계약금 입금 전", "서명 전", "계약 직후"]


class ContractCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class SituationRequest(BaseModel):
    """계약 상황 입력 (사용자 흐름 3단계): 계약 유형 + 계약 단계."""

    contract_type: ContractType
    contract_stage: ContractStage


class ContractResponse(BaseModel):
    id: int
    title: str
    contract_type: str | None
    contract_stage: str | None
    registry_case_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
