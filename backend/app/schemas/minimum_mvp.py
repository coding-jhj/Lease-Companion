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
    # 데모·OCR 충실도 비교용. 켜면 디지털 PDF도 이미지로 렌더링해 OCR로 읽는다.
    # ⚠️ 원문 이미지가 PII 비식별 전에 외부 API로 나간다 — 평시 기본값 유지.
    force_ocr: bool = False


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
