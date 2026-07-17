"""사용자 피드백 API — 계약 건 단위 등록·이력 조회.

신규 API 추가(팀 규칙: 목록 추가는 자유, openapi.json 재생성으로 공유).
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.routes.contracts import _get_owned_contract
from app.core.db import get_db
from app.models.feedback import UserFeedback
from app.models.user import User
from app.schemas.feedback import FeedbackCreateRequest, FeedbackResponse

router = APIRouter(prefix="/api/contracts/{contract_id}/feedback", tags=["feedback"])


@router.post("", status_code=201, response_model=FeedbackResponse)
def create_feedback(
    contract_id: int,
    body: FeedbackCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserFeedback:
    """피드백 등록 — 이력으로 쌓이며 수정·삭제하지 않는다."""
    contract = _get_owned_contract(contract_id, user, db)
    feedback = UserFeedback(
        contract_id=contract.id, user_id=user.id, content=body.content, rating=body.rating
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("", response_model=list[FeedbackResponse])
def list_feedback(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserFeedback]:
    """본인 계약 건의 피드백 이력 (최신순)."""
    contract = _get_owned_contract(contract_id, user, db)
    return list(
        db.scalars(
            select(UserFeedback)
            .where(UserFeedback.contract_id == contract.id)
            .order_by(UserFeedback.id.desc())
        )
    )
