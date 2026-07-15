# PoC 범위

> PoC는 **최종 MVP 기술의 실현 가능성을 검증하는 단계**다. MVP(`mvp-scope.md`)와 서로 다른 기능 목록이 아니다. PoC에서 검증한 기술을 MVP 사용자 서비스에 통합한다.

## 입력

- 계약서 (샘플)
- 등기사항증명서 (샘플)

## 처리 흐름

1. 계약서·등기사항증명서 샘플 입력
2. PDF·OCR(디지털 PyMuPDF·PDF.js / 스캔·사진 Gemini 3.5 Flash VLM 통합) 입력 처리 검증
3. 필드 추출과 정규화
4. 상용 LLM 구조화(Gemini 3.5 Flash) — 로컬 7B는 선택 비교 추론
5. 핵심 판정 6개
6. 규칙 기반 문서 교차검증
7. RAG 공식 근거 연결
8. 구조화 JSON 출력
9. 모델 비교평가

## 검증 목표

- 디지털 PDF 직접 추출·OCR(Gemini 3.5 Flash VLM 통합)이 스캔·사진 문서를 처리하는가
- 추출·정규화가 주소·금액·날짜·이름을 비교 가능한 형태로 만드는가
- 상용 LLM(Gemini 3.5 Flash)이 조항 유형·명확성 후보를 구조화 JSON으로 분류하는가 (로컬 7B는 선택 비교 실험)
- 규칙 엔진이 문서 내부 판정과 문서 교차검증(핵심 판정 6개)을 수행하는가
- RAG가 공식 근거를 검색해 연결하는가
- 베이스 7B vs 파인튜닝 7B, 상용 LLM 단독 vs 하이브리드 파이프라인 비교평가

## 핵심 판정 6개 (PoC)

MVP 12개 판정 중 PoC에서 우선 검증하는 6개. 구체 항목 선정은 판정 명세에서 관리한다: [../data/judgment-spec.md](../data/judgment-spec.md).

## 출력

- 구조화 JSON (추출값·정규화값·조항 분류·판정 상태·근거)

## 비고

- 구체 성능 수치·목표치는 미정. 실제 측정 전 임의로 만들지 않는다.
- 지표 정의·기록 형식: [../ai/evaluation-plan.md](../ai/evaluation-plan.md), [../ai/evaluation-matrix.md](../ai/evaluation-matrix.md).
