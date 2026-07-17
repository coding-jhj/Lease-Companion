"""체크리스트·계약 직후 행동 상태 API 요청·응답 wrapper.

항목 내용은 통합 AnalysisRunResult(및 A 3단계 생성 산출물)가 원본 —
여기는 항목별 확인 상태(done)만 다룬다.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ItemKind = Literal["checklist", "post_action"]


class ItemStateRequest(BaseModel):
    done: bool


class ItemStateResponse(BaseModel):
    kind: ItemKind
    item_key: str
    done: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
