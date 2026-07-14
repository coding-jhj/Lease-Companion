"""디지털 PDF의 텍스트 레이어를 읽는 최소 MVP 인식기."""

from __future__ import annotations


class DocumentReadError(ValueError):
    """업로드 문서를 텍스트로 읽을 수 없을 때 발생한다."""


def extract_document_text(content: bytes, filename: str) -> tuple[str, str]:
    """(텍스트, 읽은 방식) 반환. 방식 = "digital"(텍스트 레이어·txt) 또는 "ocr"(스캔·이미지)."""
    if not content:
        raise DocumentReadError("빈 파일은 처리할 수 없습니다.")

    lowered = filename.lower()
    if lowered.endswith(".txt"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentReadError("텍스트 파일은 UTF-8 형식이어야 합니다.") from exc
        text = text.strip()
        if not text:
            raise DocumentReadError("빈 텍스트 파일입니다.")
        return text, "digital"

    if lowered.endswith(".pdf"):
        try:
            import fitz  # type: ignore[import-not-found]
        except ImportError as exc:
            raise DocumentReadError(
                "PDF 처리를 위해 PyMuPDF 설치가 필요합니다. "
                "`pip install -e ai -e backend`를 실행하세요."
            ) from exc

        try:
            with fitz.open(stream=content, filetype="pdf") as document:
                text = "\n".join(page.get_text("text") for page in document)
        except Exception as exc:  # PyMuPDF가 세부 예외를 여러 형식으로 반환한다.
            raise DocumentReadError("유효한 PDF 파일을 읽지 못했습니다.") from exc
        text = text.strip()
        if text:
            return text, "digital"  # 디지털 PDF: 텍스트 레이어 사용(OCR 불필요 — 비용·정확도 우위)
        return _ocr_text(content, filename), "ocr"  # 텍스트 레이어 없음 = 스캔 PDF → OCR

    if lowered.endswith((".jpg", ".jpeg", ".png")):
        return _ocr_text(content, filename), "ocr"

    raise DocumentReadError("PDF·이미지(jpg·png)·UTF-8 TXT 파일만 업로드할 수 있습니다.")


def _ocr_text(content: bytes, filename: str) -> str:
    """스캔 PDF·이미지 → 상용 LLM(Gemini) VLM OCR. 실패 시 DocumentReadError로 변환."""
    from .ocr import OcrError, ocr_document

    try:
        text = ocr_document(content, filename).strip()
    except OcrError as exc:
        raise DocumentReadError(f"스캔·이미지 문서 OCR에 실패했습니다: {exc}") from exc
    if not text:
        raise DocumentReadError("OCR 결과가 비어 있습니다. 다른 파일을 사용하거나 값을 수동 입력하세요.")
    return text
