from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# 대상 계약 3종 (루트 AGENTS.md 확정)
ContractType = Literal["전세", "보증부 월세", "일반 월세"]


class ContractCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class SituationRequest(BaseModel):
    """계약 상황 입력 (사용자 흐름 3단계): 계약 유형 + 계약 단계."""

    contract_type: ContractType
    # TODO: 단계 값 목록 팀 확정 전까지 자유 문자열
    contract_stage: str = Field(min_length=1, max_length=50)


class ContractResponse(BaseModel):
    id: int
    title: str
    contract_type: str | None
    contract_stage: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
