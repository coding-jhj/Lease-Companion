# 추출 설계

## 역할

계약 문서에서 핵심 필드를 추출한다. 디지털 PDF는 PyMuPDF 텍스트를 구조화하고, 스캔 PDF·이미지는 원본에서 고정 Pydantic 필드를 Gemini VLM 1회 호출로 직접 추출한다.

## 인식·추출 흐름

1. **검증·분류 (`ingestion`)**: 실제 형식·크기·페이지·픽셀을 검사한다. 디지털 PDF는 텍스트를 추출하고 스캔·사진은 VLM 경로로 분류한다.
2. **필드 추출 (`extraction`)**: 디지털 텍스트를 구조화하거나 스캔 원본에서 `ContractFields`·`RegistryFields`를 직접 생성한다. 스캔 입력은 외부 호출 1회다.
3. **정규화 (`normalization`)**: 주소·금액·날짜·이름을 비교 가능한 형태로 정규화. (`rule-engine-design.md` 입력)

MVP 문서: 계약서·특약(필수), 등기사항증명서·중개대상물 확인설명서(선택). 필드 상세: [`../data/document-fields.md`](../data/document-fields.md).

## 추출 대상

- 임대인, 목적물 주소, 보증금·월세·계약금·잔금, 계약 기간·지급일·입주일, 관리비, 주요 특약, 등기 소유자·입금 계좌 명의 등 (판정 J01–J13에 필요한 필드)

## 구조화 출력 원칙

- 모든 추출 결과는 구조화 스키마(`ai/src/lease_companion_ai/schemas/`)로 반환한다.
- 추출값(문서에서 읽은 값)만 담는다. 로컬 모델 분류·규칙 판정·생성값과 섞지 않는다.
- 읽을 수 없거나 근거가 부족한 필드는 추측하지 않고 `미기재` / `확인 불가`로 표기한다.
- 추출은 판정하지 않는다. 값을 읽어 반환할 뿐이다. 최종 판정은 규칙 엔진이 한다.
- 추출값은 분석 전에 사용자가 **확인·수정**할 수 있어야 한다.

## 확정 (2026-07-14 선정표 + 같은 날 OCR 변경 결정)

- OCR: **상용 LLM Gemini 3.5 Flash VLM 통합** (별도 OCR·VLM 단계 없음). 디지털 PDF는 **PyMuPDF·PDF.js**. PaddleOCR-VL-1.6은 (선택) 비교실험. → [`../decisions/2026-07-14-ocr-gemini-integration.md`](../decisions/2026-07-14-ocr-gemini-integration.md)
- 필드 구조화용 상용 LLM: **Gemini 3.5 Flash**.

## 미정 (TODO)

- 이미지·PDF 전처리 방식, 필드별 신뢰도 표기 여부
