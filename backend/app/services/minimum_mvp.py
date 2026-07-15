"""최소 MVP 분석 흐름 오케스트레이션."""

from __future__ import annotations

import base64
import binascii
from typing import Any

from lease_companion_ai.pipelines.minimum_mvp import MAX_FILE_SIZE, analyze_verified_fields, extract_documents


class MinimumMvpInputError(ValueError):
    pass


def _decode(content: str) -> bytes:
    if len(content) > (MAX_FILE_SIZE * 4 // 3) + 16:
        raise MinimumMvpInputError("파일당 최대 크기는 10MB입니다.")
    try:
        return base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise MinimumMvpInputError("파일 인코딩이 올바르지 않습니다.") from exc


def extract(request: Any) -> dict[str, Any]:
    try:
        return extract_documents(
            _decode(request.contract.content_base64), request.contract.filename,
            _decode(request.registry.content_base64), request.registry.filename,
            force_ocr=request.force_ocr,
        )
    except ValueError as exc:
        raise MinimumMvpInputError(str(exc)) from exc


def analyze(request: Any) -> list[dict[str, Any]]:
    if not request.user_confirmed:
        raise MinimumMvpInputError("추출값 확인 완료 후에만 분석할 수 있습니다.")
    return analyze_verified_fields(request.contract_fields, request.registry_fields)
