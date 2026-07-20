# 인증과 영속 저장

> 회원 인증과 계약 건 단위 영속 저장의 **현재 구현과 후속 설계 방향**을 기록한다.
> 기능 확정 + 방식 확정(2026-07-16): DB **PostgreSQL**, 인증 **JWT Bearer + bcrypt 계열 해시**
> (→ [`../decisions/2026-07-16-mvp-platform-stack.md`](../decisions/2026-07-16-mvp-platform-stack.md)). 구현은 PyJWT + Passlib-bcrypt, Access Token 24시간(로컬 MVP 임시값).
> 루트 [`AGENTS.md`](../../AGENTS.md) 기준. 정확한 공개 API는 [`../api/openapi.json`](../api/openapi.json)을 따른다.

## 왜 세션이 아니라 사용자·계약 건인가

기존 설계는 단일 분석 세션 중심이었다. 현재 기준은 **로그인한 사용자**가 여러 **계약
건(ContractProject)** 을 관리하고, 각 계약 건 단위로 분석 결과·체크리스트·계약 직후
행동 상태를 **저장·재조회**하는 구조다. 분석은 1회성 세션으로 끝나지 않는다.

- 사용자 흐름 1단계(회원가입·로그인) → 2단계(계약 대시보드·계약 건 생성)에서 모델의 뿌리가 `User` → `ContractProject`로 정해진다.
- 이후 문서·추출값·분석 실행·결과·체크리스트·행동은 모두 특정 계약 건에 매달린다.

## 회원 인증

**확정**

- 회원가입·로그인 필요. 사용자는 자신의 계약 건·문서·결과만 접근한다.
- 계약 건 소유권 확인: 요청 사용자 == `ContractProject` 소유자 (계약 건 식별자는 `contract_id`).
- 개인정보·문서 내용을 로그에 남기지 않는다. 비밀정보는 `.env`에서 읽는다.
- 인증 방식: **JWT Bearer(PyJWT)**, 비밀번호 해시: **Passlib-bcrypt**, Access Token 만료: **24시간 임시값** (2026-07-16 확정).

**미정 (TODO)**

- refresh token 여부, 토큰 폐기, 운영 서명 키 관리 방식, 운영용 만료 시간
- 소셜 로그인 여부

구현은 `app/api/dependencies/`(현재 사용자 주입)와 `app/core/`(보안 유틸)에서 담당한다.

## 계약 건 단위 영속 저장

**확정**

- 영속 저장 **필요**. 계약 건(`contract_id`) 단위로 저장·재조회. `case_id`는 합성·평가 fixture 전용.
- 추출값과 생성값을 구분해 저장한다. 사용자 수정값은 `user_corrected_value`로 최초 추출값과 분리한다.
- 규칙 엔진 판정을 저장 시점에 LLM·로컬 모델이 변경하지 않는다.
- 데이터베이스: **PostgreSQL** (2026-07-16 확정). 벡터 데이터베이스(RAG용): **Chroma 로컬 모드**.
- 도메인 데이터 타입은 `ai/src/lease_companion_ai/schemas/`의 Pydantic 공통 타입을 재사용한다(→ [`../decisions/2026-07-16-shared-pydantic-schema.md`](../decisions/2026-07-16-shared-pydantic-schema.md)).

**현재 구현 / TODO**

- SQLAlchemy 영속 모델과 PostgreSQL 테이블 구조는 구현됐다.
- Alembic 마이그레이션 체계는 도입됐다(baseline + `analysis_runs` classification 컬럼 리비전, → [`../decisions/2026-07-17-alembic-migration.md`](../decisions/2026-07-17-alembic-migration.md)). 별도 repository 계층은 아직 구현하지 않았다(라우트·워커가 SQLAlchemy 세션을 직접 사용).
- 업로드 원본 파일의 보존 기간·암호화·삭제 정책은 TODO다.

### 도메인 엔터티

| 엔터티 | 역할 |
|--------|------|
| `User` | 회원 계정 |
| `ContractProject` | 계약 건. 사용자 소유, 분석의 저장 단위 |
| `Document` | 업로드 문서(계약서·등기 등) |
| `ExtractedField` | 문서에서 추출한 필드 값 (사용자 확인·수정 대상) |
| `AnalysisRun` | 분석 실행 1회 (표준 명칭, 동의어 `AnalysisJob`) |
| `JudgmentResult` | 판정 결과 (상태 9개·시급도 5개 표현) |
| `EvidenceSource` | 판정 근거 (원문 증거·공식 자료) |
| `QuestionCard` | 임대인·중개사 확인 질문 |
| `ChecklistItem` | 서명 전 체크리스트 항목 |
| `PostContractAction` | 계약 직후 행동 및 상태 |
| `UserFeedback` | 사용자 피드백 |

### 저장 대상

- 추출값 (`ExtractedField`, 사용자 수정 반영본 포함)
- 판정 (`JudgmentResult`) 및 근거 (`EvidenceSource`), 질문 (`QuestionCard`)
- 체크리스트 상태 (`ChecklistItem`)
- 계약 직후 행동 상태 (`PostContractAction`)
- 사용자 피드백 (`UserFeedback`)

### 현재 물리 저장 구조

- `User` 1 — N `ContractProject`
- `ContractProject` 1 — N `Document` · `ExtractionRun` · `CorrectionRecord` · `InputSnapshotRecord` · `AnalysisRun` · `ChecklistItemState` · `UserFeedback`
- 원본 추출 JSON은 `ExtractionRun`, 수정은 append-only `CorrectionRecord`, 확인 입력은 불변 `InputSnapshotRecord`에 저장한다.
- 규칙 판정·원문 증거·공식 근거는 `AnalysisRun.result`, 생성 설명·질문·행동은 `AnalysisRun.generation_result`, 조항 분류 결과는 `AnalysisRun.classification_result` JSON에 분리 저장한다. 분류 실패 사유의 단일 원본은 `classification_result.fallback_reason_code`이며, `classification_error`는 성공·safe fallback 모두 항상 `None`으로 두고 중복 저장하지 않는다(provider 원문·PII 저장 금지, data-contract-v1 기준).

## 관련 계층

- `app/api/dependencies/` — 인증 주체·DB 세션 주입, 계약 건 소유권 확인
- `app/repositories/` — 목표 저장소 경계. 현재 별도 구현은 없고 라우트·워커가 SQLAlchemy 세션을 직접 사용
- `app/models/` — 구현된 SQLAlchemy 영속 모델
- `app/core/` — 설정·보안 유틸
