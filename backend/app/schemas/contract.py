from datetime import date, datetime

from pydantic import BaseModel, Field

# 도메인 enum은 통합 스키마 단일 원본에서 import (data-contract-v1 5절 — 중복 정의 금지)
from lease_companion_ai.schemas.unified import ContractStage, ContractType


class ContractCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class SituationRequest(BaseModel):
    """계약 상황 입력 (사용자 흐름 3단계). 필드 구성은 통합 ContractContext 기준.

    deposit_paid 이하 5개는 기존 클라이언트·mock 호환을 위해 선택 입력(None 허용).
    분석 실행 시 ContractContext가 필수값을 최종 검증한다.
    """

    contract_type: ContractType
    contract_stage: ContractStage
    deposit_paid: bool | None = None
    signed: bool | None = None
    move_in_date: date | None = None
    balance_payment_date: date | None = None
    is_proxy_contract: bool | None = None  # null = 모름 (통합 스키마 규약)


class ContractResponse(BaseModel):
    id: int
    title: str
    contract_type: ContractType | None
    contract_stage: ContractStage | None
    deposit_paid: bool | None
    signed: bool | None
    move_in_date: date | None
    balance_payment_date: date | None
    is_proxy_contract: bool | None
    registry_case_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
