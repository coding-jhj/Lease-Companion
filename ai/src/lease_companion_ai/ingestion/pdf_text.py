"""업로드 문서를 검증하고 디지털 텍스트 또는 VLM 경로로 분류한다."""

from __future__ import annotations

from .limits import DocumentValidationError, validate_document


class DocumentReadError(ValueError):
    """업로드 문서를 읽거나 검증할 수 없을 때 발생한다."""


def extract_document_text(content: bytes, filename: str, force_ocr: bool = False) -> tuple[str, str]:
    """(텍스트, 방식)을 반환한다. 스캔·이미지는 빈 문자열과 ``vlm``을 반환한다.

    스캔 입력을 평문 OCR로 변환하지 않는다. 호출자는 원본을 고정 Pydantic 스키마의
    Gemini VLM 구조화 함수에 한 번만 전달해야 한다.
    """
    try:
        document = validate_document(content, filename, force_vlm=force_ocr)
    except DocumentValidationError as exc:
        raise DocumentReadError(str(exc)) from exc
    if document.requires_vlm:
        return "", "vlm"
    return document.digital_text or "", "digital"
