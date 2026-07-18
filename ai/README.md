# ai/

슬기로운 계약생활의 AI 처리 계층. Python 패키지 `lease_companion_ai`.

## 목적

계약 문서를 인식(디지털 PDF 직접 추출·스캔/사진 OCR은 상용 LLM Gemini 3.5 Flash VLM 통합)해 핵심 필드를 추출·정규화하고, 상용 LLM(Gemini 3.5 Flash)이 조항 유형·불명확성 후보를 구조화한다. Python 규칙 엔진이 문서 내부 판정과 문서 교차검증으로 최종 판정을 내리고, 공식자료 RAG가 근거를 검색한다. 저신뢰 결과 재검토와 쉬운 설명·확인 질문·체크리스트·계약 직후 행동 생성은 상용 LLM(GPT-5.6 Sol)이 담당한다. guardrail이 단정 표현·근거 없는 출력을 차단한다. 로컬 7B 조항 분류는 (선택) 상용 vs 로컬 성능비교 실험으로만 유지하며 MVP 크리티컬 패스에서 제외한다.

## 파이프라인

```
문서 입력 → 디지털 PDF 텍스트 추출 또는 스캔 원본 Gemini 1회 구조화 → 정규화
  → 사용자 확인·수정
  → 상용 LLM 조항 구조화·불명확성 후보 (Gemini 3.5 Flash)
     ※ (선택) 로컬 7B 성능비교 실험 — MVP 크리티컬 패스 제외
  → 규칙 엔진 문서 내부 판정·교차검증 (최종 판정)
  → 공식자료 RAG 근거
  → 저신뢰 결과 상용 LLM 재검토
  → 쉬운 설명·질문·체크리스트·행동 생성 (GPT-5.6 Sol)
  → guardrail → 저장(backend)
```

`routing`이 단계별 처리 모델·fallback을 선택한다. 상세: [`../docs/ai/`](../docs/ai/).

## 컴포넌트 책임

- **상용 LLM 구조화 (`classification`/`providers`)**: MVP 조항 유형·명확성 후보 구조화·필드 추출은 Gemini 3.5 Flash.
- **로컬 7B (`local_model`)**: (선택) 상용 vs 로컬 성능비교 실험용. MVP 크리티컬 패스 제외. 최종 판정 안 함, 규칙 결과 변경 안 함, 근거 없이 행동 확정 안 함.
- **규칙 엔진 (`rules`)**: 문서 내부 판정·교차검증 최종 판정. 결정론적.
- **RAG (`rag`)**: 공식 근거만. 판정 안 함.
- **상용 LLM (`providers`)**: 구조화·추출 Gemini 3.5 Flash, 저신뢰 재검토 + 설명·질문·행동 생성 GPT-5.6 Sol. 규칙 판정 변경 안 함.
- **guardrails / routing**: 출력 제한 / 모델·fallback 선택.

## 하위 구조

```
src/lease_companion_ai/
  ingestion/      파일 형식·자원 검증, 디지털 PDF 직접 추출(PyMuPDF), 스캔 VLM 경로 분류
  extraction/     인식 결과에서 핵심 필드 추출 (Gemini 3.5 Flash)
  normalization/  추출값 정규화(주소·금액·날짜·이름)
  local_model/    로컬 7B 조항 분류 — (선택) 성능비교 실험, MVP 크리티컬 패스 아님
  classification/ local_model 출력을 조항 유형·명확성 후보 구조로 정리
  rules/          문서 내부 판정·교차검증 (최종 판정)
  rag/            공식 근거 검색
  providers/      상용 LLM·임베딩 제공자 어댑터
  generation/     쉬운 설명·질문·체크리스트·행동 생성
  guardrails/     단정 표현·근거 없는 출력 제한
  routing/        단계별 처리 모델·fallback 선택
  evaluation/     서비스 파이프라인 컴포넌트별·end-to-end 평가 실행
  pipelines/      PoC·MVP 흐름 연결
  schemas/        AI 입출력 구조 — 런타임 통합 스키마의 Pydantic 단일 원본 (Backend가 재사용)
prompts/          extraction/questions/checklists/summaries 프롬프트 원본·버전
training/         로컬 7B QLoRA 파인튜닝(선택 성능비교 실험) 설정·전처리·평가·메타데이터 (가중치 제외)
tests/            컴포넌트별·전체 흐름 테스트
```

## 저장해야 하는 파일

- AI 로직 코드, 프롬프트 원본, AI 입출력 스키마, 평가·테스트 코드
- 로컬 7B 파인튜닝(선택 성능비교 실험) 설정·전처리·평가·메타데이터 (`training/`)

## 저장하면 안 되는 파일

- 실제 계약서·개인정보 (→ 절대 금지, 비식별·합성 데이터만)
- LLM API 키·비밀정보 (→ `.env`)
- 로컬 7B 가중치·체크포인트, 대용량 벡터 인덱스 (→ Git 제외)
- 백엔드 API 라우팅·서비스 코드 (→ `backend/`)

## 다른 폴더와의 연결

- `backend/`가 이 패키지의 파이프라인을 호출하고 결과를 영속 저장한다. AI 로직을 backend에 중복 구현하지 않는다.
- 라벨·파인튜닝 데이터셋·RAG 자료·평가 데이터는 `data/`에서 참조한다.
- 설계 문서는 `docs/ai/`.

## 추후 분리 가능성

로컬 모델 기능(선택 성능비교 실험)은 `local_model/` 인터페이스로 결합도를 낮춘다. 별도 모델 서버 배포가 확정되면 `services/model-api`로 분리할 수 있다. 현재는 `ai/` 내부에 둔다. (`../docs/ai/local-model-plan.md`)

## 현재 상태 / TODO

- 구현됨(최소 MVP 범위): `ingestion`(형식·크기·페이지·픽셀 검증, PyMuPDF), `extraction`(스캔 원본 Gemini 1회 구조화·디지털 텍스트 구조화·정규식 폴백), `normalization`, `rules`(R01~R10·J01~J12), `pipelines`, canonical `schemas` v1.8.0 + 관련 테스트.
- 구현됨(RAG 배치 1~4): 공식 출처 manifest·법령 원문 2개, 내부 계약·결정적 청킹·BM25, Chroma·Gemini embedding·Cohere rerank 어댑터, hybrid/RRF·fallback, R01~R10 공식 근거 enrichment, dev/test retrieval 평가. 기본 런타임은 Gemini 키가 있으면 영속 Chroma+BM25 Hybrid/RRF를 사용하고 Cohere 키가 있으면 rerank를 추가한다. 키·provider·인덱스 실패 시 BM25로 축소한다. 외부 실호출 smoke test는 별도 승인 전 미수행이다.
- 구현됨(생성 배치 4~5 + A10 offline): 생성 Pydantic 계약·provider protocol·fake provider·버전 프롬프트·결정적 fallback, 외부 요청 PII 토큰화, 금지 단정·grounding·source ID·규칙 불변 Guardrail, OpenAI Responses API `gpt-5.6-sol` provider와 opt-in CASE-001 smoke 경계. Backend worker가 규칙 결과와 생성 결과를 분리 저장하며 키가 없으면 template fallback을 사용한다. 실제 유료 smoke는 미수행.
- 미구현·후속: `classification` 독립 계층, GPT 저신뢰 재검토 경로, 독립 `routing` 구현, `local_model`, retrieval 외 평가 실행기, J 결과 공식 근거 검색.
- 확정(2026-07-14): 상용 LLM Gemini 3.5 Flash(구조화·추출)·GPT-5.6 Sol(생성·재검토). 공식 API model ID는 `gpt-5.6-sol`; 실제 유료 호출은 키·비용 승인 후 수행.
- 확정(2026-07-14 변경): 스캔 PDF·이미지는 Gemini 3.5 Flash가 원본에서 고정 Pydantic 필드를 1회 호출로 직접 추출한다. 디지털 PDF는 PyMuPDF 텍스트 경로다. PaddleOCR-VL은 선택 비교실험이다 (`../docs/decisions/2026-07-14-ocr-gemini-integration.md`).
- 확정·구현(offline 경계): 임베딩 gemini-embedding-001+BM25·리랭커 Cohere rerank-v4.0-pro·Chroma 로컬 모드. 실제 유료 호출 smoke test는 별도 승인 필요 (`../docs/decisions/2026-07-16-mvp-platform-stack.md`).
- 구현 완료(2026-07-18): `schemas/`의 Pydantic 모델 v1.8.0이 런타임 통합 스키마 단일 원본이며 `RuleResult`·`JudgmentInput`·`JudgmentResult`·`RuleGuidance`·`JudgmentGuidance`·`GuidanceActionItem`·`StageGuidance`·생성 `prompt_version` 계약을 포함한다 (`../docs/decisions/2026-07-16-shared-pydantic-schema.md`).
- 구현 완료(2026-07-18): R01~R10 기반 분석을 유지하면서 J01~J12 결정론적 판정과 Backend 저장·조회 세로 슬라이스를 연결했다.
- TODO: 로컬 7B 베이스 모델(선택 성능비교 실험 — MVP 크리티컬 패스 아님) → `local_model`/`training` 구현 (`../docs/ai/fine-tuning-plan.md`)
