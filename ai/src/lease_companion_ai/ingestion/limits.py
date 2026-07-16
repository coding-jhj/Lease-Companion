"""업로드 문서 자원 제한과 형식 검증의 단일 원본."""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path


def _positive_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name}은 양의 정수여야 합니다.") from exc
    if value <= 0:
        raise RuntimeError(f"{name}은 양의 정수여야 합니다.")
    return value


# 로컬 MVP 임시값. 운영 트래픽·비용 측정 후 환경변수로 조정한다.
MAX_FILE_SIZE = _positive_env("DOCUMENT_MAX_FILE_BYTES", 10 * 1024 * 1024)
MAX_PDF_PAGES = _positive_env("DOCUMENT_MAX_PDF_PAGES", 20)
MAX_IMAGE_DIMENSION = _positive_env("DOCUMENT_MAX_IMAGE_DIMENSION", 6_000)
MAX_IMAGE_PIXELS = _positive_env("DOCUMENT_MAX_IMAGE_PIXELS", 40_000_000)
MAX_PDF_RENDER_PIXELS = _positive_env("DOCUMENT_MAX_PDF_RENDER_PIXELS", 80_000_000)
MAX_CONCURRENT_VLM_CALLS = _positive_env("DOCUMENT_MAX_CONCURRENT_VLM_CALLS", 2)
MAX_EXTERNAL_CALLS_PER_REQUEST = _positive_env("DOCUMENT_MAX_EXTERNAL_CALLS_PER_REQUEST", 2)
PDF_VALIDATION_DPI = _positive_env("DOCUMENT_PDF_VALIDATION_DPI", 150)


class DocumentValidationError(ValueError):
    """업로드 파일이 형식 또는 자원 제한을 충족하지 못함."""


@dataclass(frozen=True, slots=True)
class ValidatedDocument:
    extension: str
    mime_type: str
    page_count: int
    requires_vlm: bool
    digital_text: str | None = None


def _image_dimensions(content: bytes, extension: str) -> tuple[int, int]:
    if extension == ".png":
        if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n":
            raise DocumentValidationError("확장자와 실제 PNG 형식이 일치하지 않습니다.")
        return struct.unpack(">II", content[16:24])
    if len(content) < 4 or content[:3] != b"\xff\xd8\xff":
        raise DocumentValidationError("확장자와 실제 JPEG 형식이 일치하지 않습니다.")
    offset = 2
    while offset + 9 < len(content):
        if content[offset] != 0xFF:
            offset += 1
            continue
        marker = content[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(content):
            break
        segment_length = int.from_bytes(content[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(content):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height = int.from_bytes(content[offset + 3 : offset + 5], "big")
            width = int.from_bytes(content[offset + 5 : offset + 7], "big")
            return width, height
        offset += segment_length
    raise DocumentValidationError("손상되었거나 크기를 확인할 수 없는 JPEG입니다.")


def validate_document(content: bytes, filename: str, *, force_vlm: bool = False) -> ValidatedDocument:
    if not content:
        raise DocumentValidationError("빈 파일은 처리할 수 없습니다.")
    if len(content) > MAX_FILE_SIZE:
        raise DocumentValidationError(f"파일당 최대 크기는 {MAX_FILE_SIZE}바이트입니다.")
    extension = Path(filename).suffix.lower()
    if extension not in {".txt", ".pdf", ".png", ".jpg", ".jpeg"}:
        raise DocumentValidationError("PDF·이미지(jpg·png)·UTF-8 TXT 파일만 업로드할 수 있습니다.")
    if extension == ".txt":
        if content.startswith((b"%PDF-", b"\x89PNG", b"\xff\xd8\xff")):
            raise DocumentValidationError("확장자와 실제 문서 형식이 일치하지 않습니다.")
        try:
            text = content.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise DocumentValidationError("텍스트 파일은 UTF-8 형식이어야 합니다.") from exc
        if not text:
            raise DocumentValidationError("빈 텍스트 파일입니다.")
        return ValidatedDocument(extension, "text/plain", 1, False, text)
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise DocumentValidationError("확장자와 실제 PDF 형식이 일치하지 않습니다.")
        try:
            import fitz  # type: ignore[import-not-found]

            with fitz.open(stream=content, filetype="pdf") as document:
                if document.needs_pass:
                    raise DocumentValidationError("암호화된 PDF는 처리할 수 없습니다.")
                page_count = document.page_count
                if page_count == 0:
                    raise DocumentValidationError("페이지가 없는 PDF는 처리할 수 없습니다.")
                if page_count > MAX_PDF_PAGES:
                    raise DocumentValidationError(f"PDF는 최대 {MAX_PDF_PAGES}쪽까지 처리할 수 있습니다.")
                total_pixels = 0
                texts: list[str] = []
                for page in document:
                    width = round(page.rect.width * PDF_VALIDATION_DPI / 72)
                    height = round(page.rect.height * PDF_VALIDATION_DPI / 72)
                    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                        raise DocumentValidationError("PDF 페이지 크기가 허용 한도를 초과합니다.")
                    total_pixels += width * height
                    if total_pixels > MAX_PDF_RENDER_PIXELS:
                        raise DocumentValidationError("PDF 전체 픽셀 수가 허용 한도를 초과합니다.")
                    texts.append(page.get_text("text", sort=True))
        except DocumentValidationError:
            raise
        except Exception as exc:
            raise DocumentValidationError("유효한 PDF 파일을 읽지 못했습니다.") from exc
        text = "\n".join(texts).strip()
        digital = len(text) >= 100 * page_count
        return ValidatedDocument(extension, "application/pdf", page_count, force_vlm or not digital, text or None)
    expected_mime = "image/png" if extension == ".png" else "image/jpeg"
    width, height = _image_dimensions(content, extension)
    if width <= 0 or height <= 0:
        raise DocumentValidationError("이미지 크기가 올바르지 않습니다.")
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise DocumentValidationError("이미지 가로·세로 크기가 허용 한도를 초과합니다.")
    if width * height > MAX_IMAGE_PIXELS:
        raise DocumentValidationError("이미지 총 픽셀 수가 허용 한도를 초과합니다.")
    try:
        import fitz  # type: ignore[import-not-found]

        with fitz.open(stream=content, filetype=extension.lstrip(".")) as image_doc:
            image_doc.load_page(0)
    except Exception as exc:
        raise DocumentValidationError("손상된 이미지 파일입니다.") from exc
    return ValidatedDocument(extension, expected_mime, 1, True)
