from datetime import datetime
from pydantic import BaseModel, Field

from lease_companion_ai.schemas.unified import ContractStage, ContractType


class ContractCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class SituationRequest(BaseModel):
    """계약 상황 입력 (사용자 흐름 3단계): 계약 유형 + 계약 단계."""

    contract_type: ContractType
    contract_stage: ContractStage


class ContractResponse(BaseModel):
    id: int
    title: str
    contract_type: ContractType | None
    contract_stage: ContractStage | None
    created_at: datetime

    model_config = {"from_attributes": True}
