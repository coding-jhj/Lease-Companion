"""최근 공개 보도자료 조회 API 응답."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecentPressReleaseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    publisher: str
    published_at: str
    source_url: str


class RecentPressReleaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_id: str
    items: list[RecentPressReleaseItem] = Field(max_length=2)
    retrieved_at: datetime
    notice: str
