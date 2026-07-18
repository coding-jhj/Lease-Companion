"""서명 전 체크리스트·계약 직후 행동 상태 API (사용자 흐름 8단계).

상태는 계약 건 단위로 저장·재조회한다. 항목 문구·근거는 분석 결과가 원본이며
여기서는 항목 식별자(item_key)별 done 상태만 관리한다.
"""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.routes.contracts import _get_owned_contract
from app.core.db import get_db
from app.models.checklist import ChecklistItemState
from app.models.user import User
from app.schemas.checklist import ITEM_KEY_PATTERN, ItemKind, ItemStateRequest, ItemStateResponse

router = APIRouter(prefix="/api/contracts/{contract_id}/checklist-items", tags=["checklists"])


@router.get("", response_model=list[ItemStateResponse])
def list_item_states(
    contract_id: int,
    kind: ItemKind | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChecklistItemState]:
    """저장된 항목 상태 재조회. kind로 체크리스트/계약 직후 행동 필터 가능."""
    contract = _get_owned_contract(contract_id, user, db)
    query = select(ChecklistItemState).where(ChecklistItemState.contract_id == contract.id)
    if kind is not None:
        query = query.where(ChecklistItemState.kind == kind)
    return list(db.scalars(query.order_by(ChecklistItemState.id)))


@router.put("/{kind}/{item_key}", response_model=ItemStateResponse)
def put_item_state(
    contract_id: int,
    kind: ItemKind,
    body: ItemStateRequest,
    item_key: str = Path(max_length=100, pattern=ITEM_KEY_PATTERN),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChecklistItemState:
    """항목 상태 저장 (upsert — 없으면 생성, 있으면 갱신)."""
    contract = _get_owned_contract(contract_id, user, db)
    if item_key.split(":", maxsplit=2)[1] != kind:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "item_kind_mismatch",
                "message": "item_key의 항목 종류가 URL kind와 일치하지 않습니다.",
            },
        )
    state = db.scalar(
        select(ChecklistItemState).where(
            ChecklistItemState.contract_id == contract.id,
            ChecklistItemState.kind == kind,
            ChecklistItemState.item_key == item_key,
        )
    )
    if state is None:
        state = ChecklistItemState(contract_id=contract.id, kind=kind, item_key=item_key)
        db.add(state)
    state.done = body.done
    db.commit()
    db.refresh(state)
    return state
