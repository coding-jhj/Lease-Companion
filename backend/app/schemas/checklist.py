"""체크리스트·계약 직후 행동 상태 API 요청·응답 wrapper.

항목 내용은 통합 AnalysisRunResult(및 A 3단계 생성 산출물)가 원본 —
여기는 항목별 확인 상태(done)만 다룬다.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from lease_companion_ai.schemas.unified import GUIDANCE_ITEM_KEY_PATTERN

ItemKind = Literal["checklist", "post_action"]
ITEM_KEY_PATTERN = GUIDANCE_ITEM_KEY_PATTERN
ItemKey = Annotated[str, StringConstraints(pattern=ITEM_KEY_PATTERN, max_length=100)]


class ItemStateRequest(BaseModel):
    done: bool


class ItemStateResponse(BaseModel):
    kind: ItemKind
    # 기존 로컬 상태도 조회 가능하게 두고, 신규 쓰기만 URL pattern으로 제한한다.
    item_key: str
    done: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
