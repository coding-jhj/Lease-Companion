"""스캔 PDF·이미지 문서를 상용 LLM(Gemini VLM)으로 OCR한다.

OCR = Gemini 3.5 Flash VLM 통합 결정(docs/decisions/2026-07-14-ocr-gemini-integration.md).
디지털 PDF는 OCR 없이 PyMuPDF로 처리(pdf_text.py) — 여기는 텍스트 레이어가 없는 스캔 PDF·이미지 전용.

⚠️ PII: 원문 이미지(성명·주민번호·계좌 포함 가능)가 외부 API(Google)로 전송된다.
   데모 단계 수용 결정(위 결정문서). 프로덕션 전 마스킹/로컬 OCR 재검토 필요.

출력은 **평문**이다. 마크다운 표를 만들지 않는다 — 하류 정규식 파서(extraction)가
'라벨: 값' 라인 패턴을 읽기 때문. (구조화는 별도 단계, 여기서 하지 않는다.)
"""
from __future__ import annotations

import os
import time
from pathlib import Path

_MODEL = "gemini-3.5-flash"   # 선정표 확정(I/O 2026 GA)
_DPI = 200                    # 스캔 PDF 래스터화 해상도

_PROMPT = (
    "이 문서 이미지의 모든 텍스트를 원문 그대로, 보이는 순서대로 평문으로 추출하라.\n"
    "- 보이는 텍스트만 옮겨라. 없는 내용 추가·추측·요약 금지.\n"
    "- 숫자·금액·날짜·이름·번호는 이미지에 보이는 문자 그대로. 단위 변환·정규화·교정 금지"
    " (예: '삼억원'을 '3억'으로 바꾸지 말 것).\n"
    "- '라벨: 값' 형태는 그대로 유지하라.\n"
    "- 표는 마크다운 표(|)로 만들지 말고, 각 칸을 원문 순서대로 평문 줄로 풀어써라.\n"
    "- 읽기 어려운 부분은 (판독 불가)로 표기하라."
)


class OcrError(RuntimeError):
    """OCR 수행 불가(키 미설정·SDK 미설치·API 실패)."""


def _client():
    envf = Path(__file__).resolve().parents[4] / ".env"  # …/ingestion/ocr.py → repo root
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise OcrError("OCR용 GEMINI_API_KEY가 설정되지 않았습니다. 레포 루트 .env에 키를 넣으세요.")
    try:
        from google import genai
    except ImportError as exc:
        raise OcrError("OCR에 google-genai가 필요합니다. `pip install google-genai`.") from exc
    return genai.Client(api_key=key)


def _ocr_images(images: list[bytes], mime: str) -> str:
    client = _client()  # 가드된 import 먼저 — google-genai 없으면 여기서 OcrError
    from google.genai import errors, types

    def _one_page(idx: int, img: bytes) -> str:
        for attempt in range(4):
            try:
                resp = client.models.generate_content(
                    model=_MODEL,
                    contents=[_PROMPT, types.Part.from_bytes(data=img, mime_type=mime)],
                )
                return resp.text or ""
            except errors.ServerError as exc:  # 503 과부하 등 일시적 → 백오프 재시도
                if attempt == 3:
                    raise OcrError(f"OCR API 호출 실패(p{idx + 1}): {exc}") from exc
                time.sleep(5 * (attempt + 1))
            except errors.APIError as exc:  # 4xx·쿼터 등 비재시도 → OcrError로 변환(500 방지)
                raise OcrError(f"OCR API 오류(p{idx + 1}): {exc}") from exc
        raise OcrError(f"OCR 재시도 소진(p{idx + 1})")  # 도달 불가 — 타입 체커용

    if len(images) == 1:
        return _one_page(0, images[0])
    # 페이지는 서로 독립 → 동시 호출. 지연의 대부분이 Gemini 출력 생성 시간이라
    # 순차 실행은 페이지 수만큼 배로 느리다(3쪽 실측 ~55초 → 병렬 ~1쪽 시간).
    # ponytail: 상한 8 — 대형 PDF가 쿼터(RPM)를 한 번에 태우는 것 방지. 429가 보이면 낮춘다.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=min(len(images), 8)) as pool:
        return "\n".join(pool.map(_one_page, range(len(images)), images))  # map = 페이지 순서 보존


def ocr_document(content: bytes, filename: str) -> str:
    """스캔 PDF·이미지 바이트 → 평문 텍스트. 디지털 PDF에는 쓰지 않는다."""
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        import fitz  # PyMuPDF

        with fitz.open(stream=content, filetype="pdf") as doc:
            images = [page.get_pixmap(dpi=_DPI).tobytes("png") for page in doc]
        return _ocr_images(images, "image/png")
    for ext, mime in ((".png", "image/png"), (".jpg", "image/jpeg"), (".jpeg", "image/jpeg")):
        if lowered.endswith(ext):
            return _ocr_images([content], mime)
    raise OcrError(f"OCR 지원 형식이 아닙니다: {filename}")
