import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from lease_companion_ai.schemas.unified import ContractContext
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.db import get_db
from app.models.analysis import (
    STATUS_COMPLETED,
    AnalysisRun,
    CorrectionRecord,
    ExtractionRun,
    InputSnapshotRecord,
)
from app.models.checklist import ChecklistItemState
from app.models.contract import ContractProject
from app.models.document import Document
from app.models.feedback import UserFeedback
from app.models.user import User
from app.schemas.contract import ContractCreateRequest, ContractResponse, SituationRequest
from app.schemas.document import RegistryLinkRequest

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


def _generated_action_keys(generation_result: dict) -> set[tuple[str, str]]:
    """최신 분석 생성결과에서 체크리스트·계약 직후 행동 항목의 (kind, item_key) 집합.

    8번 화면(ContractDetailPage)이 쓰는 것과 동일한 소스 — items + judgment_items.
    """
    keys: set[tuple[str, str]] = set()
    groups = (generation_result.get("items") or []) + (
        generation_result.get("judgment_items") or []
    )
    for group in groups:
        for entry in group.get("signing_checklist_items") or []:
            keys.add(("checklist", entry["item_key"]))
        for entry in group.get("post_contract_action_items") or []:
            keys.add(("post_action", entry["item_key"]))
    return keys


def _action_status(contract_id: int, db: Session) -> Literal["none", "in_progress", "done"]:
    """대시보드 행동 상태: none/in_progress/done. done 항목이 전체 항목과 같으면 done."""
    run = db.scalar(
        select(AnalysisRun)
        .where(
            AnalysisRun.contract_id == contract_id,
            AnalysisRun.status == STATUS_COMPLETED,
            AnalysisRun.generation_result.isnot(None),
        )
        .order_by(AnalysisRun.id.desc())
        .limit(1)
    )
    if run is None or not run.generation_result:
        return "none"
    keys = _generated_action_keys(run.generation_result)
    if not keys:
        return "none"
    done_keys = {
        (state.kind, state.item_key)
        for state in db.scalars(
            select(ChecklistItemState).where(
                ChecklistItemState.contract_id == contract_id,
                ChecklistItemState.done.is_(True),
            )
        )
    }
    done_count = len(keys & done_keys)
    if done_count == 0:
        return "none"
    if done_count == len(keys):
        return "done"
    return "in_progress"

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
) -> list[ContractResponse]:
    """대시보드용 본인 계약 건 목록 (최신 생성 순, 행동 상태 포함)."""
    contracts = db.scalars(
        select(ContractProject)
        .where(ContractProject.user_id == user.id)
        .order_by(ContractProject.id.desc())
    )
    responses: list[ContractResponse] = []
    for contract in contracts:
        response = ContractResponse.model_validate(contract)
        response.action_status = _action_status(contract.id, db)
        responses.append(response)
    return responses


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
    # FK 자식 행을 먼저 지운다 (cascade 미설정 — Postgres는 남은 자식이 있으면 삭제 거부).
    # correction_records 는 extraction_runs 를 참조하므로 그보다 먼저.
    # ponytail: 앱 코드로 처리. 테이블이 더 늘면 FK ON DELETE CASCADE 마이그레이션으로 승격.
    for model in (
        CorrectionRecord,
        Document,
        ExtractionRun,
        InputSnapshotRecord,
        AnalysisRun,
        ChecklistItemState,
        UserFeedback,
    ):
        db.execute(delete(model).where(model.contract_id == contract_id))
    db.delete(contract)
    db.commit()
