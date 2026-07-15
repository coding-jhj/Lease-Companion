"""디지털 PDF의 텍스트 레이어를 읽는 최소 MVP 인식기."""

from __future__ import annotations

# 디지털 판정 최소 글자수/페이지. 이 밑이면 텍스트 레이어가 껍데기(스캔본의 워터마크·
# 페이지번호·머리글)라고 보고 OCR로 넘긴다.
# ponytail: 문서 평균 기준 휴리스틱. 실측 근거 — 가상 등기부·계약서 6페이지에서 가장
# 희박한 진짜 디지털 페이지가 369자, 부스러기는 수십 자 수준이라 그 사이를 잡았다.
# 천장: 디지털+스캔이 섞인 문서는 평균이 스캔 페이지를 가린다. 실제 스캔본을 확보하면
# 페이지 단위 판정 + 부분 OCR 병합으로 올린다.
_MIN_CHARS_PER_PAGE = 100


class DocumentReadError(ValueError):
    """업로드 문서를 텍스트로 읽을 수 없을 때 발생한다."""


def extract_document_text(content: bytes, filename: str, force_ocr: bool = False) -> tuple[str, str]:
    """(텍스트, 읽은 방식) 반환. 방식 = "digital"(텍스트 레이어·txt) 또는 "ocr"(스캔·이미지).

    force_ocr=True면 텍스트 레이어가 멀쩡해도 OCR로 읽는다(데모·OCR 충실도 비교용).
    ⚠️ 디지털 PDF를 강제 OCR하면 로컬 처리로 막고 있던 원문 이미지가 PII 비식별 전에
       외부 API로 나간다. 평시 경로에서 켜지 않는다.
    """
    if not content:
        raise DocumentReadError("빈 파일은 처리할 수 없습니다.")

    lowered = filename.lower()
    if lowered.endswith(".txt"):  # 이미지가 없어 OCR 대상이 아니다 — force_ocr도 해당 없음
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

        # force_ocr여도 먼저 연다 — 깨진 PDF를 OCR로 넘기면 ocr.py의 fitz.open이 그대로 터진다.
        try:
            with fitz.open(stream=content, filetype="pdf") as document:
                # sort=True: 표 셀을 읽기 순서로 정렬한다. extraction의 표 파서가
                # 라벨 다음 줄에서 값을 찾으므로 좌표 순서가 아니라 읽기 순서여야 한다.
                text = "\n".join(page.get_text("text", sort=True) for page in document)
                page_count = document.page_count
        except Exception as exc:  # PyMuPDF가 세부 예외를 여러 형식으로 반환한다.
            raise DocumentReadError("유효한 PDF 파일을 읽지 못했습니다.") from exc
        text = text.strip()
        if not force_ocr and len(text) >= _MIN_CHARS_PER_PAGE * max(page_count, 1):
            return text, "digital"  # 디지털 PDF: 텍스트 레이어 사용(OCR 불필요 — 비용·정확도 우위)
        return _ocr_text(content, filename), "ocr"  # 텍스트 레이어 없음·껍데기 = 스캔 PDF → OCR

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
