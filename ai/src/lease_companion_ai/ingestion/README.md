# ingestion/

## 책임

업로드 문서의 실제 형식·크기·페이지·픽셀을 검증한다. 디지털 PDF·TXT는 텍스트를 반환하고, 스캔 PDF·이미지는 원본을 `extraction`의 Gemini 고정 스키마 1회 호출로 넘긴다. **규칙 판정은 하지 않는다.**

⚠️ OCR이 상용 API로 바뀌면서 **원문 이미지가 PII 비식별 전에 외부로 전송**된다. 데모 단계 수용 결정 — 프로덕션 전 재검토 필수. (`../../../../docs/decisions/2026-07-14-ocr-gemini-integration.md`)

## 하위 구조

- `limits.py` — 업로드 형식·크기·PDF 페이지·가로세로·총 픽셀·동시성·요청당 호출 제한의 단일 원본
- `pdf_text.py` — 디지털 PDF·TXT 직접 추출, 스캔 PDF·이미지를 `vlm` 경로로 분류
- `../extraction/gemini_extractor.py` — 스캔 원본에서 `ContractFields` 또는 `RegistryFields`를 1회 호출로 직접 생성
- `document_classifier/` — 계약서 / 등기사항증명서 / 건축물대장 등 문서 종류 판별
- `quality_check/` — 해상도·잘림·판독 가능성 점검, 저품질 시 재업로드 신호

## 입력

- 사용자가 업로드한 원본 문서 (PDF·이미지)

## 출력

- 검증된 문서 형식 + 디지털 텍스트 또는 VLM 처리 표시
- 판독 불가 시 `분석 불가` 시급도로 반환

## 확정 / TODO

- 확정(2026-07-14 변경): 디지털 PDF=PyMuPDF·PDF.js, 스캔 PDF·이미지=Gemini VLM 고정 Pydantic 스키마 1회 구조화. 평문 OCR 후 재구조화하는 2회 호출은 사용하지 않는다.
- 로컬 MVP 임시 기본값: 파일 10MiB, PDF 20쪽, 이미지 한 변 6000px, 이미지 4천만px, PDF 환산 8천만px, 동시 VLM 2회, 사용자 요청당 외부 호출 2회. 환경변수명과 기본값은 `limits.py`가 단일 원본이다.
- OCR 충실도(금액 오독·환각)·비용·지연 미측정 (TODO)
- 문서 종류 판별 기준·라벨 집합 확정 필요 (TODO)
