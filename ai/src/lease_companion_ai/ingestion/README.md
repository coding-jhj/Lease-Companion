# ingestion/

## 책임

업로드된 계약 문서를 인식해 후속 추출이 쓸 수 있는 텍스트·레이아웃으로 변환한다. PDF는 직접 추출(PyMuPDF·PDF.js)하고, 스캔·이미지는 OCR(상용 LLM Gemini 3.5 Flash VLM 통합)로 처리한다. 문서 종류를 판별하고 입력 품질을 점검한다. **추출·판정은 하지 않는다.**

⚠️ OCR이 상용 API로 바뀌면서 **원문 이미지가 PII 비식별 전에 외부로 전송**된다. 데모 단계 수용 결정 — 프로덕션 전 재검토 필수. (`../../../../docs/decisions/2026-07-14-ocr-gemini-integration.md`)

## 하위 구조

- `pdf_text.py` — 텍스트 레이어 PDF·TXT 직접 추출, 텍스트 레이어 없으면 OCR 폴백 (구현 완료)
- `ocr.py` — 스캔 PDF·이미지 문서 OCR (상용 LLM Gemini 3.5 Flash VLM 통합) (구현 완료)
- `document_classifier/` — 계약서 / 등기사항증명서 / 건축물대장 등 문서 종류 판별
- `quality_check/` — 해상도·잘림·판독 가능성 점검, 저품질 시 재업로드 신호

## 입력

- 사용자가 업로드한 원본 문서 (PDF·이미지)

## 출력

- 문서 종류 라벨 + 페이지별 텍스트·레이아웃 + 품질 상태
- 판독 불가 시 `분석 불가` 시급도로 반환

## 확정 / TODO

- 확정(2026-07-14 변경): 디지털 PDF=PyMuPDF·PDF.js, OCR=상용 LLM Gemini 3.5 Flash VLM 통합 (별도 OCR·VLM 단계 없음). PaddleOCR-VL-1.6은 (선택) 비교실험
- OCR 충실도(금액 오독·환각)·비용·지연 미측정 (TODO)
- 문서 종류 판별 기준·라벨 집합 확정 필요 (TODO)
