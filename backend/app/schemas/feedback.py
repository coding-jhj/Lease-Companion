from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreateRequest(BaseModel):
    """피드백 등록: 자유 텍스트 필수 + 평점(1~5) 선택."""

    content: str = Field(min_length=1, max_length=2000)
    rating: int | None = Field(default=None, ge=1, le=5)


class FeedbackResponse(BaseModel):
    id: int
    contract_id: int
    content: str
    rating: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
