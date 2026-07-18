# API 개요

> API **책임 영역**만 기록한다. 확정되지 않은 경로·메서드·스키마는 `TODO`로 표시한다.
> **구현된 API의 정확한 요청·응답 스키마**: [`openapi.json`](openapi.json) (서버 코드에서 자동 생성 — 갱신: `backend/`에서 `python -c "from app.main import app; import json, pathlib; pathlib.Path('../docs/api/openapi.json').write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding='utf-8')"`).
> 서버를 켜면 같은 내용을 http://localhost:8000/docs (Swagger UI)에서 화면으로 보고 직접 호출 테스트도 가능.
> 도메인·계층 상세는 [`docs/backend/auth-and-persistence.md`](../backend/auth-and-persistence.md) 참조.

분석은 단일 세션이 아니라 로그인한 사용자의 **계약 건(ContractProject) 단위**로 저장·재조회한다.

## 책임 영역 (9개)

| 영역 | 책임 | 관련 도메인 | 상태 |
|------|------|-------------|------|
| `auth` | 회원가입·로그인·JWT Bearer 토큰 발급 (2026-07-16 인증 방식 확정) | User | **구현됨**: `POST /api/auth/signup`(username·email·password, 201, 중복 시 409 `username_taken`/`email_taken`) · `POST /api/auth/login`(username·password → TokenResponse) · `GET /api/auth/me`. 라이브러리 PyJWT + Passlib-bcrypt. 토큰 만료 24h 확정(2026-07-16). TODO: refresh token |
| `users` | 사용자 프로필·계정 조회·관리 | User | TODO: 경로 미정 |
| `contracts` | 계약 건(`contract_id`) 생성·조회·목록(대시보드), 계약 상황 입력 | ContractProject | **구현됨**: `POST /api/contracts`(title, 201) · `GET /api/contracts`(본인 것만, 최신순) · `GET /api/contracts/{id}` · `PUT /api/contracts/{id}/situation`(contract_type: 전세/보증부 월세/일반 월세 + contract_stage: 계약금 입금 전/서명 전/계약 직후 — 2026-07-16 팀 확정) · `DELETE /api/contracts/{id}`(204). 남의 계약 건·없는 건 → 404 `not_found` |
| `documents` | 계약서·등기 등 문서 업로드, 형식·크기 검증, 이력 관리 | Document | **구현됨**: `POST /api/contracts/{id}/documents`(multipart: file + doc_type[계약서/등기사항증명서/중개대상물 확인설명서], pdf·jpg·png + 합성 샘플 txt, 20MB 이하, 201) · `GET /api/contracts/{id}/documents`(이력 전체, 최신순). 모의 등기 연결 `POST /api/contracts/{id}/registry-link`(`{case_id}` — data/sample/registry-records fixture 검증, 계약 건 응답의 `registry_case_id`에 저장) |
| `extractions` | AI 추출 실행(비동기), 추출값 반환, 사용자 확인·수정 반영 | ExtractedField | **구현됨**: `POST /api/contracts/{id}/extractions`(업로드 계약서 + 등기 문서·모의 등기 연결로 추출 시작, 202) · `GET …/extractions/latest`(상태 폴링 + 완료 시 수정 반영된 통합 DocumentExtraction JSON) · `POST …/corrections`(통합 CorrectionRequest — 원본 보존, 이력 저장) · `POST …/extractions/confirm`(서버 측 불변 InputSnapshot 생성, 201) |
| `analyses` | 분석 실행(상용 LLM 구조화(Gemini 3.5 Flash)·규칙 엔진·RAG·상용 LLM 생성(GPT-5.6 Sol); 선택 로컬 7B 실험), 상태 조회 | AnalysisRun | **구현됨**: `POST /api/contracts/{id}/analysis-runs`(최신 확인 완료 스냅샷으로 비동기 실행 시작, 202) · `GET …/analysis-runs`(재분석 이력, 최신순) · `GET …/analysis-runs/{analysis_run_id}`(**폴링** — status: pending/running/completed/failed, 완료 시 result에 통합 AnalysisRunResult JSON). 상태 전달은 폴링 확정(2026-07-16 팀 회의) |
| `results` | 판정·원문 증거·공식 근거·질문 리포트 조회 | JudgmentResult, EvidenceSource, QuestionCard | 독립 `results` 경로는 두지 않고 `GET /api/contracts/{id}/analysis-runs/{analysis_run_id}`의 `result`·`generation_result`에서 조회 |
| `checklists` | 서명 전 체크리스트·계약 직후 행동 상태 관리 | ChecklistItem, PostContractAction | **구현됨**: `GET /api/contracts/{id}/checklist-items`(?kind=checklist/post_action 필터) · `PUT …/checklist-items/{kind}/{item_key}`(`{done}` upsert — 계약 건 단위 저장·재조회). 항목 문구·근거는 생성 결과가 원본이며 상태만 저장. item_key는 `R01/J01:checklist:<hash>` / `R01/J01:post_action:<hash>` 안정 식별자(→ `docs/decisions/2026-07-18-guidance-action-item-keys.md`). Backend는 신규 쓰기의 형식과 kind 일치를 검증 |
| `feedback` | 사용자 피드백 수집 | UserFeedback | **구현됨**(2026-07-17 신규 추가 — 목록 추가는 자유 규칙): `POST /api/contracts/{id}/feedback`(content 1~2000자 필수 + rating 1~5 선택, 201) · `GET /api/contracts/{id}/feedback`(본인 것만, 최신순). 이력으로 쌓기만 하고 수정·삭제 없음 |

> 영역 ↔ 도메인은 1:1이 아니다. `auth`·`users`는 모두 `User`를 다루고, `results`는 판정·근거·질문을 함께 조회하며, `checklists`는 체크리스트와 계약 직후 행동을 함께 관리한다.

## 결과 표현 기준

- 결과 상태 9개·시급도 5개·판정 12항목(J01–J12)은 루트 [`AGENTS.md`](../../AGENTS.md)를 단일 기준으로 참조한다. 본 문서에서 재정의하지 않는다.
- `안전`/`위험`/`사기 가능성 점수` 같은 종합 판정 API는 두지 않는다.

## 원칙

- 계층 분리: API 라우트 → 의존성 → 서비스 → 저장소.
- 모든 입력·업로드 파일 검증.
- `RuleStatus`·`urgency`는 규칙 엔진만 결정한다. RAG 근거가 없으면 판정을 유지하고 `evidence_sources=[]`로 반환한다.
- 공통 오류 형식 사용 ([`error-format.md`](error-format.md)).
- 스키마 변경 시 본 문서와 프론트엔드 타입 동기화.

## 확정 / 미정 (TODO)

- 확정(2026-07-16): 인증 방식 **JWT Bearer + bcrypt 계열**(→ [`../decisions/2026-07-16-mvp-platform-stack.md`](../decisions/2026-07-16-mvp-platform-stack.md)). 요청·응답의 도메인 타입은 `ai/src/lease_companion_ai/schemas/` Pydantic 공통 타입을 재사용(→ [`../decisions/2026-07-16-shared-pydantic-schema.md`](../decisions/2026-07-16-shared-pydantic-schema.md)).
- 구현 경로·메서드·요청/응답 스키마의 단일 기준은 [`openapi.json`](openapi.json)이다. 새 경로는 서버 코드와 OpenAPI를 함께 갱신한다.
- 확정(구현): JWT 라이브러리 PyJWT, 해시 Passlib-bcrypt. 오류 응답은 422 포함 전부 `{"error": {"code", "message", "details?"}}` ([`error-format.md`](error-format.md) 초안 채택)
- 확정(구현): 비밀번호 규칙 — 8자 이상(최대 72), 영문·숫자·특수문자 각 1자 이상 포함. 프론트엔드는 같은 규칙으로 제출 전 안내
- 확정(2026-07-16): 토큰 만료 **24h** (refresh 없음, 만료 시 재로그인)
- TODO: refresh token·토큰 폐기·서명 키 관리
- 확정(현재 로컬 MVP): 추출·분석 상태는 HTTP 폴링으로 전달한다. 운영용 별도 작업 큐·재시도 정책은 TODO다.
- 확정(구현): 모의 등기 연결은 `POST /api/contracts/{id}/registry-link`다.
