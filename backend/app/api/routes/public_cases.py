"""판정과 분리된 최근 공개 보도자료 조회 API."""

from datetime import datetime, timezone

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.public_case import RecentPressReleaseResponse
from app.services.public_press_releases import (
    PublicPressReleaseSourceError,
    fetch_recent_press_releases,
)


router = APIRouter(prefix="/api/public-cases", tags=["public-cases"])


@router.get(
    "/recent-press-releases",
    response_model=RecentPressReleaseResponse,
)
def get_recent_press_releases(
    pattern_id: Annotated[str, Query(pattern=r"^DP0[1-8]$")],
    user: User = Depends(get_current_user),
) -> RecentPressReleaseResponse:
    """선택한 피해 유형과 관련된 최근 공식 보도자료를 최대 2건 조회한다."""

    del user
    try:
        items = fetch_recent_press_releases(pattern_id=pattern_id, limit=2)
    except PublicPressReleaseSourceError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "public_source_unavailable",
                "message": "공개 보도자료를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
            },
        ) from exc
    return RecentPressReleaseResponse(
        pattern_id=pattern_id,
        items=[item.__dict__ for item in items],
        retrieved_at=datetime.now(timezone.utc),
        notice="외부 공개 보도자료이며 현재 계약의 판정 근거가 아닙니다.",
    )
