"""디지털 PDF의 텍스트 레이어를 읽는 최소 MVP 인식기."""

from __future__ import annotations


class DocumentReadError(ValueError):
    """업로드 문서를 텍스트로 읽을 수 없을 때 발생한다."""


def extract_document_text(content: bytes, filename: str) -> str:
    if not content:
        raise DocumentReadError("빈 파일은 처리할 수 없습니다.")

    lowered = filename.lower()
    if lowered.endswith(".txt"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentReadError("텍스트 파일은 UTF-8 형식이어야 합니다.") from exc
    elif lowered.endswith(".pdf"):
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
    else:
        raise DocumentReadError("PDF 또는 UTF-8 TXT 파일만 업로드할 수 있습니다.")

    text = text.strip()
    if not text:
        raise DocumentReadError(
            "텍스트 레이어를 찾지 못했습니다. 스캔 PDF OCR은 아직 지원하지 않으므로 "
            "텍스트 PDF를 사용하거나 값을 수동 입력하세요."
        )
    return text
