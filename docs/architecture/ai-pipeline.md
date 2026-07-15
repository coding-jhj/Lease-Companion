# AI 파이프라인

계약 문서 입력부터 저장까지의 단계별 흐름과 컴포넌트 책임을 정의한다. 각 단계 출력은 구조화 스키마(`ai/src/lease_companion_ai/schemas/`)를 따르고, `pipelines`가 PoC·MVP 흐름을 각각 연결한다.

## 단계 흐름

```
문서 입력
  → PDF 직접 추출(PyMuPDF·PDF.js) 또는 OCR(상용 LLM Gemini 3.5 Flash VLM 통합)
  → 핵심 필드 추출
  → 사용자 확인·수정        ← 사용자 개입 지점 (분석 전)
  → 상용 LLM 조항 구조화·불명확성 후보(Gemini 3.5 Flash)   ← (선택)로컬 7B 성능비교 실험은 MVP 크리티컬 패스 제외
  → Python 규칙 엔진 문서 내부 판정·교차검증   ← 최종 판정
  → 공식자료 RAG (근거)
  → 저신뢰 결과 상용 LLM 재검토
  → 쉬운 설명·질문·체크리스트·행동 생성
  → Guardrail
  → 저장
```

## 단계별 책임

| 단계 | 모듈(예상) | 책임 |
|------|-----------|------|
| 문서 인식 | `ingestion` | 디지털 PDF는 텍스트 직접 추출(PyMuPDF·PDF.js), 스캔 PDF·사진은 OCR(상용 LLM Gemini 3.5 Flash VLM). VLM은 Gemini에 통합되어 레이아웃·표를 함께 획득(별도 OCR·VLM 단계 없음) |
| 추출 | `extraction` | 인식 결과에서 핵심 필드(임대인·주소·보증금·기간·특약 등) 구조화 추출 |
| 정규화 | `normalization` | 주소·금액·날짜·이름을 비교 가능한 형태로 정규화 |
| 사용자 확인·수정 | (backend 경유) | 추출값을 사용자가 확인·수정. 이후 단계는 **확인·수정본**을 입력으로 사용 |
| 조항 구조화 | 상용 LLM(Gemini 3.5 Flash) / (선택)`local_model` | MVP는 상용 LLM(Gemini 3.5 Flash)이 조항 유형 분류·명확/불명확/확인 필요 후보 분류·책임 주체·조건 구조화. (선택)로컬 7B는 성능비교 실험용(MVP 크리티컬 패스 제외) |
| 규칙 엔진 | `rules` | 문서 내부 판정 + 문서 교차검증(등기사항증명서 등)의 **명시적 최종 판정** |
| RAG | `rag` | 공식 법령·표준계약서·공공 가이드에서 판정 근거 검색 |
| 상용 LLM 재검토·생성 | `generation` | 저신뢰 결과 재검토, 근거 기반 쉬운 설명·질문·체크리스트·계약 직후 행동 생성 |
| Guardrail | `guardrails` | 단정 표현·근거 없는 출력 차단 |
| Routing | `routing` | 단계별 처리 모델·fallback 선택 |

## 컴포넌트 원칙

- **추출은 문서 인식(PDF·OCR·VLM) 담당이다.** MVP 조항 분류·불명확성 후보는 **상용 LLM(Gemini 3.5 Flash)**이 담당하며 **최종 판정을 내리지 않는다.** (선택)로컬 7B는 상용 vs 로컬 성능비교 실험용으로만 유지하고 MVP 크리티컬 패스에서 제외한다.
- **규칙 엔진이 명시적 최종 판정을 내린다.** 로컬 7B·상용 LLM은 규칙 엔진 결과를 **임의로 변경하지 않는다.**
- **RAG는 근거만 검색한다. 판정하지 않는다.** 근거가 없으면 추측하지 않고 `확인 불가` 또는 `확인 필요`로 반환한다.
- **상용 LLM은 저신뢰 결과 재검토와 생성만 담당한다.** 규칙 판정을 바꾸지 않는다.
- 추출값(문서에서 읽은 값)과 생성값(모델이 만든 설명·질문·요약)을 구분한다.
- Guardrail을 통과한 출력만 저장한다. 프롬프트는 버전 관리한다.
- 결과 표현은 판정 상태 9개·시급도 5개를 따르고 종합 판정을 사용하지 않는다(정의는 [`../../AGENTS.md`](../../AGENTS.md), [`../data/judgment-spec.md`](../data/judgment-spec.md)).

## 관련 문서

- (선택)로컬 7B 성능비교 실험·서빙 방향: `local-model-plan`(예정)
- 파인튜닝 계획: `fine-tuning-plan`(예정)
- 모델·fallback 라우팅: `model-routing`(예정)
- 단계별 평가: [`../ai/evaluation-plan.md`](../ai/evaluation-plan.md), 평가 매트릭스 `evaluation-matrix`(예정)

## 미정 (TODO)

- 상용 LLM 확정: 조항 구조화 Gemini 3.5 Flash, 설명·질문·행동 생성 GPT-5.6 Sol. 임베딩·검색 확정: gemini-embedding-001 + BM25, 리랭커 Cohere rerank-v4.0-pro. OCR 확정: 상용 LLM Gemini 3.5 Flash VLM 통합(디지털 PDF는 PyMuPDF·PDF.js), 별도 OCR·VLM 단계 없음(2026-07-14 변경, → [`../decisions/2026-07-14-ocr-gemini-integration.md`](../decisions/2026-07-14-ocr-gemini-integration.md)). PaddleOCR-VL은 (선택) 비교실험. 벡터 저장소 제품 미정.
- (선택)로컬 7B 성능비교 실험용 베이스 모델은 실험 진행 시 확정.
- 저신뢰 판단 기준(재검토로 넘길 임계값)·routing fallback 정책 확정 필요.
