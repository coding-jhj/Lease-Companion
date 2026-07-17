import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from lease_companion_ai.schemas.unified import ContractContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.db import get_db
from app.models.contract import ContractProject
from app.models.user import User
from app.schemas.contract import ContractCreateRequest, ContractResponse, SituationRequest
from app.schemas.document import RegistryLinkRequest

router = APIRouter(prefix="/api/contracts", tags=["contracts"])

# 모의 등기 fixture 위치 (기본: 저장소 data/sample/registry-records)
_DEFAULT_REGISTRY_DIR = Path(__file__).resolve().parents[4] / "data" / "sample" / "registry-records"


def _registry_file(case_id: str) -> Path | None:
    """case_id에 해당하는 모의 등기 파일. 두 가지 파일명 관례를 모두 허용
    (CASE-001 → registry_CASE-001.txt 또는 registry_001.txt)."""
    registry_dir = Path(os.environ.get("REGISTRY_DIR", _DEFAULT_REGISTRY_DIR))
    candidates = [f"registry_{case_id}.txt", f"registry_{case_id.replace('CASE-', '')}.txt"]
    for name in candidates:
        if (registry_dir / name).is_file():
            return registry_dir / name
    return None


def _contract_context(contract: ContractProject) -> ContractContext:
    """계약 상황 입력 → canonical ContractContext. 필수값 미입력이면 422.

    필수: contract_type·contract_stage·deposit_paid·signed (A 확정, 2026-07-17).
    move_in_date·balance_payment_date·is_proxy_contract는 null 허용.
    """
    required = {
        "contract_type": contract.contract_type,
        "contract_stage": contract.contract_stage,
        "deposit_paid": contract.deposit_paid,
        "signed": contract.signed,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "missing_contract_context",
                "message": f"계약 상황 입력이 필요합니다. 누락: {', '.join(missing)}",
            },
        )
    return ContractContext.model_validate(
        {
            "contract_id": contract.id,
            "contract_type": contract.contract_type,
            "contract_stage": contract.contract_stage,
            "deposit_paid": contract.deposit_paid,
            "signed": contract.signed,
            "move_in_date": contract.move_in_date,
            "balance_payment_date": contract.balance_payment_date,
            "is_proxy_contract": contract.is_proxy_contract,
        }
    )


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
    contract.contract_type = body.contract_type.value
    contract.contract_stage = body.contract_stage.value
    contract.deposit_paid = body.deposit_paid
    contract.signed = body.signed
    contract.move_in_date = body.move_in_date
    contract.balance_payment_date = body.balance_payment_date
    contract.is_proxy_contract = body.is_proxy_contract
    db.commit()
    db.refresh(contract)
    return contract


@router.post("/{contract_id}/registry-link", response_model=ContractResponse)
def link_registry(
    contract_id: int,
    body: RegistryLinkRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContractProject:
    """모의 등기 데이터 연결 (2026-07-16 팀 합의 API). 규칙 엔진 교차검증에 사용."""
    contract = _get_owned_contract(contract_id, user, db)
    if _registry_file(body.case_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "해당 case_id의 모의 등기 데이터가 없습니다."},
        )
    contract.registry_case_id = body.case_id
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
