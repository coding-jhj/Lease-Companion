from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.db import get_db
from app.models.contract import ContractProject
from app.models.user import User
from app.schemas.contract import ContractCreateRequest, ContractResponse, SituationRequest

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


def _get_owned_contract(contract_id: int, user: User, db: Session) -> ContractProject:
    """본인 소유 계약 건만 반환. 남의 것·없는 것 모두 404 (존재 여부 노출 방지)."""
    contract = db.scalar(
        select(ContractProject).where(
            ContractProject.id == contract_id, ContractProject.user_id == user.id
        )
    )
    if contract is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "계약 건을 찾을 수 없습니다."},
        )
    return contract


@router.post("", status_code=201, response_model=ContractResponse)
def create_contract(
    body: ContractCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContractProject:
    contract = ContractProject(user_id=user.id, title=body.title)
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


@router.get("", response_model=list[ContractResponse])
def list_contracts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ContractProject]:
    """대시보드용 본인 계약 건 목록 (최신 생성 순)."""
    return list(
        db.scalars(
            select(ContractProject)
            .where(ContractProject.user_id == user.id)
            .order_by(ContractProject.id.desc())
        )
    )


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContractProject:
    return _get_owned_contract(contract_id, user, db)


@router.put("/{contract_id}/situation", response_model=ContractResponse)
def put_situation(
    contract_id: int,
    body: SituationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContractProject:
    """계약 상황 입력 (사용자 흐름 3단계). 재입력 시 덮어씀."""
    contract = _get_owned_contract(contract_id, user, db)
    contract.contract_type = body.contract_type
    contract.contract_stage = body.contract_stage
    db.commit()
    db.refresh(contract)
    return contract


@router.delete("/{contract_id}", status_code=204)
def delete_contract(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    contract = _get_owned_contract(contract_id, user, db)
    db.delete(contract)
    db.commit()
