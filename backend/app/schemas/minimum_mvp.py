"""최소 MVP 데모 API 요청·응답 모델."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EncodedDocument(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)


class ExtractionRequest(BaseModel):
    contract: EncodedDocument
    registry: EncodedDocument


class ExtractionResponse(BaseModel):
    contract: dict[str, Any]
    registry: dict[str, Any]


class AnalysisRequest(BaseModel):
    contract_fields: dict[str, Any]
    registry_fields: dict[str, Any]
    user_confirmed: bool


class AnalysisResponse(BaseModel):
    results: list[dict[str, Any]]
    disclaimer: str
