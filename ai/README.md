# ai/

슬기로운 계약생활의 AI 처리 계층. Python 패키지 `lease_companion_ai`.

## 목적

계약 문서를 인식(디지털 PDF 직접 추출·스캔/사진 OCR은 상용 LLM Gemini 3.5 Flash VLM 통합)해 핵심 필드를 추출·정규화하고, 상용 LLM(Gemini 3.5 Flash)이 조항 유형·불명확성 후보를 구조화한다. Python 규칙 엔진이 문서 내부 판정과 문서 교차검증으로 최종 판정을 내리고, 공식자료 RAG가 근거를 검색한다. 저신뢰 결과 재검토와 쉬운 설명·확인 질문·체크리스트·계약 직후 행동 생성도 상용 LLM(Gemini 3.5 Flash)이 담당한다. guardrail이 단정 표현·근거 없는 출력을 차단한다. 로컬 7B 조항 분류는 (선택) 상용 vs 로컬 성능비교 실험으로만 유지하며 MVP 크리티컬 패스에서 제외한다.

## 파이프라인

```
문서 입력 → 디지털 PDF 텍스트 추출 또는 스캔 원본 Gemini 1회 구조화 → 정규화
  → 사용자 확인·수정
  → 상용 LLM 조항 구조화·불명확성 후보 (Gemini 3.5 Flash)
     ※ (선택) 로컬 7B 성능비교 실험 — MVP 크리티컬 패스 제외
  → 규칙 엔진 문서 내부 판정·교차검증 (최종 판정)
  → 공식자료 RAG 근거
  → 저신뢰 결과 상용 LLM 재검토
  → 쉬운 설명·질문·체크리스트·행동 생성 (Gemini 3.5 Flash)
  → guardrail → 저장(backend)
```

`routing`이 단계별 처리 모델·fallback을 선택한다. 상세: [`../docs/ai/`](../docs/ai/).

## 컴포넌트 책임

- **상용 LLM 구조화 (`extraction`/`classification`/`providers`)**: Gemini 3.5 Flash가 필드 추출과 조항 유형·명확성 후보 구조화를 담당한다. `classification`은 추출과 분리된 canonical 입력·결과, provider, safe fallback, 분석 연결까지 구현됐다.
- **로컬 7B (`local_model`)**: (선택) 상용 vs 로컬 성능비교 실험용. MVP 크리티컬 패스 제외. 최종 판정 안 함, 규칙 결과 변경 안 함, 근거 없이 행동 확정 안 함.
- **규칙 엔진 (`rules`)**: 문서 내부 판정·교차검증 최종 판정. 결정론적.
- **RAG (`rag`)**: 공식 근거만. 판정 안 함.
- **상용 LLM (`providers`)**: 구조화·추출과 저신뢰 재검토 + 설명·질문·행동 생성 모두 Gemini 3.5 Flash. 규칙 판정 변경 안 함.
- **guardrails / routing**: 출력 제한 / 모델·fallback 선택.

## 하위 구조

```
src/lease_companion_ai/
  ingestion/      파일 형식·자원 검증, 디지털 PDF 직접 추출(PyMuPDF), 스캔 VLM 경로 분류
  extraction/     인식 결과에서 핵심 필드 추출 (Gemini 3.5 Flash)
  normalization/  추출값 정규화(주소·금액·날짜·이름)
  local_model/    로컬 7B 조항 분류 — (선택) 성능비교 실험, MVP 크리티컬 패스 아님
  classification/ 추출과 분리된 조항 유형·명확성 후보 서비스·safe fallback
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

- 구현됨(실전 계약 점검): `ingestion`(형식·크기·페이지·픽셀 검증, PyMuPDF), `extraction`(스캔 원본 Gemini 구조화·디지털 텍스트 구조화·정규식 폴백), `normalization`, `classification`(Gemini provider·safe fallback), `rules`(R01~R24·J01~J13), `pipelines`, canonical `schemas` v1.8.0 읽기 호환·v1.9.0 신규 출력 경로. Backend worker가 classification과 규칙 결과를 내부 저장한다.
- 구현됨(RAG·특약): 공식 출처 manifest는 `official_verified` 10건이며 그중 재배포 조건을 충족한 로컬 source 6건을 사용한다. 결정적 청킹·BM25, Chroma·Gemini embedding·Cohere rerank 어댑터, hybrid/RRF·fallback, R/J 근거 enrichment, 특약 6유형 매칭·검색·생성·Guardrail·평가를 구현했다. key·provider·인덱스 실패 시 로컬 BM25 또는 빈 근거로 축소한다. 실제 외부 provider 품질 검증은 미수행이다.
- 구현됨(생성 배치 4~5 + A10 offline): 생성 Pydantic 계약·provider protocol·fake provider·버전 프롬프트·결정적 fallback, 외부 요청 PII 토큰화, 금지 단정·grounding·source ID·규칙 불변 Guardrail, Gemini `gemini-3.5-flash` provider와 opt-in CASE-001 smoke 경계. Backend worker가 규칙 결과와 생성 결과를 분리 저장하며 키가 없으면 template fallback을 사용한다. 실제 유료 smoke는 미수행.
- 구현됨(평가·routing): 추출·사용자 수정·R/J 규칙·RAG·생성·Guardrail·PII·end-to-end offline 평가와 provider 오류·할당량·응답 검증 실패 분류, provider→결정적 fallback·embedding→BM25·Cohere→hybrid fallback 실행 계층.
- 구현됨(계약 연습): 승인 시나리오 3개, 답변 평가·상태 머신, Gemini/Fake provider, Backend 세션·턴·결과 API, Frontend 텍스트 대화·복기 흐름.
- 미구현·후속: 선택 실험 `local_model`, 실제 Gemini·Cohere provider 품질·비용 검증, routing 전용 품질 평가, 연습 미디어·음성, 운영 배포.
- 변경 확정(2026-07-20): 상용 LLM Gemini 3.5 Flash가 구조화·추출과 생성·재검토를 담당한다. 공식 API model ID는 `gemini-3.5-flash`; 실제 유료 호출은 키·비용 승인 후 수행.
- 확정(2026-07-14 변경): 스캔 PDF·이미지는 Gemini 3.5 Flash가 원본에서 고정 Pydantic 필드를 1회 호출로 직접 추출한다. 디지털 PDF는 PyMuPDF 텍스트 경로다. PaddleOCR-VL은 선택 비교실험이다 (`../docs/decisions/2026-07-14-ocr-gemini-integration.md`).
- 확정·구현(offline 경계): 임베딩 gemini-embedding-001+BM25·리랭커 Cohere rerank-v4.0-pro·Chroma 로컬 모드. 실제 유료 호출 smoke test는 별도 승인 필요 (`../docs/decisions/2026-07-16-mvp-platform-stack.md`).
- 구현 완료(2026-07-19): `schemas/`의 Pydantic 모델이 런타임 통합 스키마 단일 원본이다. v1.9.0은 v1.8.0 읽기 호환과 `ClassificationInput`·`ClassificationResult`·fallback provenance 계약을 추가했다. Frontend는 두 버전을 지원하며, Backend worker는 classification 실행 결과를 내부 저장하고 API에는 노출하지 않는다 (`../docs/decisions/2026-07-18-classification-boundary.md`).
- 구현 완료(2026-07-18): R01~R10 기반 분석을 유지하면서 J01~J12 결정론적 판정과 Backend 저장·조회 세로 슬라이스를 연결했다.
- TODO: 로컬 7B 베이스 모델(선택 성능비교 실험 — MVP 크리티컬 패스 아님) → `local_model`/`training` 구현 (`../docs/ai/fine-tuning-plan.md`)
