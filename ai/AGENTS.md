# ai/AGENTS.md

`ai/` 전용 지시서. 루트 [`../AGENTS.md`](../AGENTS.md)를 단일 기준으로 전제하며, 여기서는 AI 모듈 고유 규칙만 정의한다. 충돌 시 루트 AGENTS.md가 우선한다.

## AI 파이프라인 (기준)

```
문서 입력
  → PDF 직접 추출(PyMuPDF·PDF.js) 또는 OCR(상용 LLM Gemini 3.5 Flash VLM 통합) (ingestion)
  → 핵심 필드 추출 (extraction, Gemini 3.5 Flash)
  → 정규화 (normalization)
  → 사용자 확인·수정            ← 분석 전, backend/frontend 경유
  → 상용 LLM 조항 구조화·명확성 후보 (classification, Gemini 3.5 Flash)
     ※ (선택) 로컬 7B 성능비교 실험 — MVP 크리티컬 패스 제외 (local_model)
  → Python 규칙 엔진 문서 내부 판정·교차검증 (rules)  ← 최종 판정
  → 공식자료 RAG 근거 (rag, gemini-embedding-001+BM25 · Cohere rerank-v4.0-pro)
  → 피해 유형 비교(risk_patterns) · 검증된 유사 참고 사례(공식 근거와 분리)
  → 저신뢰 결과 상용 LLM 재검토 (routing → providers, Gemini 3.5 Flash)
  → 쉬운 설명·질문·체크리스트·행동 생성 (generation, Gemini 3.5 Flash)
  → guardrail (guardrails)
  → 저장                        ← backend
```

`routing`이 각 단계에서 처리 모델과 fallback을 선택한다. `pipelines`가 PoC·MVP 흐름을 각각 연결한다.

## 컴포넌트 책임 구분

- **상용 LLM 구조화 (`classification`)**: MVP 조항 유형·명확성(명확/불명확/확인 필요) 후보 구조화와 필드 추출은 상용 LLM(Gemini 3.5 Flash)이 담당한다.
- **로컬 7B 모델 (`local_model`)**: **(선택) 상용 vs 로컬 성능비교 실험용 — MVP 크리티컬 패스 제외.** 파인튜닝(B/C안)으로 조항 유형·명확성 후보 분류, 책임 주체·조건 구조화를 검증한다. **최종 판정을 내리지 않고, 규칙 엔진 결과를 변경하지 않으며, 근거 없이 사용자 행동을 확정하지 않는다.**
- **Python 규칙 엔진 (`rules`)**: 문서 내부 판정과 문서 교차검증의 **명시적 최종 판정**. 결정론적 규칙으로 동작한다. 로컬 모델·상용 LLM이 규칙 결과를 임의로 변경하지 않는다.
- **RAG (`rag`)**: 검증된 공식 자료 기반 **근거 검색**만 담당한다. `RuleStatus`·`urgency`를 변경하지 않는다. 근거가 없으면 `evidence_sources=[]`로 반환하고 생성 설명에서만 공식 근거 확인 필요를 알린다.
- **상용 LLM (`providers`)**: 조항 구조화·필드 추출과 저신뢰 결과 재검토·근거 기반 쉬운 설명·질문·행동 생성은 Gemini 3.5 Flash. 규칙 판정을 바꾸지 않는다.
- **생성 (`generation`)**: 쉬운 설명·확인 질문·서명 전 체크리스트·계약 직후 행동 생성. 상용 LLM을 `routing` 경유로 호출한다.
- **guardrails**: 단정 표현(가능·안전·사기·합법 판정)과 근거 없는 출력을 차단한다.
- **routing**: 단계별 처리 모델·fallback 선택. 상용 LLM 우선, 할당량·장애 시 fallback. (`docs/ai/model-routing.md`)

## 결과 표현 (루트 판정 범위 기준)

- 공통 결과 상태 9개: `일치` · `불일치` · `명확` · `불명확` · `미기재` · `상충 가능` · `확인 필요` · `확인 불가` · `적용 제외`
- 시급도 5개(상태와 별도): `즉시 확인` · `계약 전 확인` · `계약 직후 조치` · `참고` · `분석 불가`
- **`안전`/`위험`/`사기 가능성 점수` 같은 종합 판정을 사용하지 않는다.**
- 판정 항목(J01–J12)과 판정별 적용 가능 상태는 [`../docs/data/judgment-spec.md`](../docs/data/judgment-spec.md)를 기준으로 한다. 각 문서에서 중복 정의하지 않고 참조한다.

## 규칙

- **추출값**(문서에서 읽은 값)과 **생성값**(모델이 만든 설명·질문·행동)을 항상 구분한다.
- 로컬 모델·규칙·RAG·상용 LLM의 산출을 섞지 않고 각 컴포넌트 책임대로 분리해 반환한다.
- 모든 AI 결과는 구조화된 스키마(`src/lease_companion_ai/schemas/`)로 반환한다. 이 경로의 **Pydantic 모델이 런타임 통합 스키마의 단일 원본(canonical runtime schema)**이며, Backend가 공통 타입을 import해 재사용한다. JSON Schema는 Pydantic에서 생성한다. → [`../docs/decisions/2026-07-16-shared-pydantic-schema.md`](../docs/decisions/2026-07-16-shared-pydantic-schema.md)
- 통합 스키마 필드 규약: 사용자 수정값 `user_corrected_value`, 확인 상태 `verification_status`, 추출 신뢰도는 3등급(`추출됨`/`불확실`/`실패`), 원문 증거는 `page`/`text`(둘 다 null 허용).
- 구현 순서: **R01~R10 기반 실전 계약 점검 MVP를 먼저 완성하고, J01~J12 전체 판정으로 후속 확장한다.** J 확장 시 기존 R01~R10 필드의 이름·의미를 바꾸지 않는다(하위 호환).
- 근거가 부족하면 추측하지 않고 `확인 필요` / `확인 불가` 상태로 반환한다.
- 프롬프트를 코드에 길게 하드코딩하지 않는다. 원본은 `prompts/`에 두고 버전을 관리한다. (`../docs/ai/prompt-management.md`)
- 로컬 7B 가중치·체크포인트는 Git에 커밋하지 않는다. `training/`에는 설정·전처리·평가·메타데이터만 둔다. (`../docs/ai/fine-tuning-plan.md`)
- 목표 성능 수치는 실제 측정 전 임의로 만들지 않는다. 지표 정의·기록 형식만 관리한다. (`../docs/ai/evaluation-matrix.md`)

## 모듈 경계

| 모듈 | 책임 |
|------|------|
| `ingestion/` | 문서 인식: PDF 직접 추출(PyMuPDF·PDF.js), OCR(상용 LLM Gemini VLM 통합 — 별도 OCR/VLM 단계 없음) |
| `extraction/` | 인식 결과에서 핵심 필드 추출 |
| `normalization/` | 추출값 정규화(주소·금액·날짜·이름) |
| `local_model/` | 로컬 7B 조항 유형·명확성 후보 분류 — (선택) 성능비교 실험용, MVP 크리티컬 패스 아님 (최종 판정 안 함) |
| `classification/` | `local_model` 출력을 조항 유형·명확성 후보 구조로 정리 (판정 안 함) |
| `rules/` | 문서 내부 판정·문서 교차검증 (최종 판정) |
| `rag/` | 공식 근거 검색 (판정 안 함) |
| `risk_patterns/` | R/J 결과를 DP01~DP08 피해 유형 관점으로 결정적으로 묶음. 판정 변경 안 함 |
| `providers/` | 상용 LLM·임베딩 제공자 어댑터 (추출·재검토·생성·검색 호출) |
| `generation/` | 쉬운 설명·질문·체크리스트·행동 생성 |
| `guardrails/` | 단정 표현·근거 없는 출력 제한 |
| `routing/` | 단계별 처리 모델·fallback 선택 |
| `evaluation/` | 서비스 파이프라인 컴포넌트별·end-to-end 평가 실행 |
| `pipelines/` | PoC·MVP 처리 흐름 연결 |
| `schemas/` | AI 입출력 구조 |

`src/` 밖(`ai/` 직속) 디렉터리:

| 디렉터리 | 책임 |
|----------|------|
| `prompts/` | 프롬프트 원본·버전 (extraction/questions/checklists/summaries) |
| `training/` | 로컬 7B QLoRA 파인튜닝(선택 성능비교 실험 — MVP 크리티컬 패스 아님) 설정·전처리·평가·메타데이터 (가중치·체크포인트 제외) |
| `tests/` | 컴포넌트별·전체 흐름 테스트 |

로컬 모델 기능은 `local_model/` 인터페이스로 분리해 결합도를 낮춘다. 별도 모델 서버 배포가 확정되면 추후 `services/model-api`로 분리할 수 있게 한다. 지금은 최상위 서비스를 추가하지 않는다.

`training/`(파인튜닝 학습·평가)과 `src/.../evaluation/`(서비스 파이프라인 평가)의 역할을 구분한다.

## 테스트

- 인식·추출·정규화·로컬 분류·규칙·검색·생성·전체 흐름 테스트를 `tests/` 하위에서 분리한다.
- 테스트하지 않은 내용을 통과했다고 쓰지 않는다.

## 확정 / 미정

확정(2026-07-14 팀 선정):
- 조항 구조화·필드 추출: 상용 LLM Gemini 3.5 Flash
- 쉬운 설명·질문·행동 생성·재검토: 상용 LLM Gemini 3.5 Flash
- OCR: 상용 LLM(Gemini 3.5 Flash) VLM 통합 (2026-07-14 변경, → ../docs/decisions/2026-07-14-ocr-gemini-integration.md). 디지털 PDF는 PyMuPDF·PDF.js. PaddleOCR-VL은 (선택) 비교실험
- 임베딩·검색: gemini-embedding-001 + BM25, 리랭커 Cohere rerank-v4.0-pro

확정(2026-07-16 팀 합의, → ../docs/decisions/2026-07-16-mvp-platform-stack.md):
- 벡터 DB: **Chroma 로컬 모드**
- 통합 스키마: `src/lease_companion_ai/schemas/` Pydantic 단일 원본 (→ ../docs/decisions/2026-07-16-shared-pydantic-schema.md)

미정 (TODO — 임의 확정·설치 금지):
- 로컬 7B 베이스 모델 (선택 성능비교 실험용 — MVP 크리티컬 패스 아님)

특정 SDK·라이브러리를 임의로 추가하지 않고 TODO로 둔다.
