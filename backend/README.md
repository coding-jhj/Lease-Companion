# backend/

슬기로운 계약생활의 API 서버. **FastAPI** (Python).

## 목적

로그인한 사용자의 **계약 건(ContractProject)** 단위로 문서·추출값·분석 실행·결과를 관리한다.
분석은 단일 세션으로 끝나지 않고 계약 건 단위로 **영속 저장·재조회**된다. backend는
프론트엔드 요청을 받아 입력·업로드 파일을 검증하고, `ai/` 파이프라인(상용 LLM 구조화 →
규칙 엔진 → RAG → 상용 LLM 생성, 로컬 7B는 선택적 성능비교 실험)을 **오케스트레이션**하며,
판정·근거·질문·행동·체크리스트를 저장한다.

## 담당 기능

- 회원가입·로그인 (JWT Bearer, PyJWT + Passlib-bcrypt 구현. refresh token·운영 키 정책 TODO)
- 계약 대시보드·계약 건 생성·조회
- 계약 상황 입력
- 계약서·등기 등 문서 업로드, 형식·크기·개수 검증
- 추출값 확인·수정 반영
- 분석 실행(상용 LLM 구조화 → 규칙 엔진 → RAG → 상용 LLM 생성, 로컬 7B는 선택적 성능비교 실험) 오케스트레이션
- 분석 상태 관리 (분석 중/완료/오류)
- 판정·원문 증거·공식 근거·질문·행동 리포트 저장·조회
- 체크리스트·계약 직후 행동 상태 관리
- 사용자 피드백 수집
- 계약 연습 시나리오 목록·세션·턴·최종 행동·복기 저장·재조회
- 공통 오류 처리

## 도메인 엔터티

루트 [`../AGENTS.md`](../AGENTS.md)와 [`docs/backend/auth-and-persistence.md`](../docs/backend/auth-and-persistence.md) 기준.

영속 모델 구현 완료: `User` · `ContractProject` · `Document` · `ExtractionRun` · `CorrectionRecord` · `InputSnapshotRecord` · `AnalysisRun` · `ChecklistItemState` · `UserFeedback`. 추출 필드와 판정·근거·질문·행동 결과는 canonical Pydantic JSON으로 실행 이력에 저장한다.

> `AnalysisRun`을 표준 명칭으로 사용한다. (루트 AGENTS.md의 `AnalysisJob`은 동의 표기)

## API 책임 영역

`auth`·`contracts`·`documents`·`extractions`·`analysis-runs`·`checklist-items`·`feedback` 경로가 구현되어 있다. 분석 결과는 완료된 `analysis-runs`의 `result`(규칙 판정)·`generation_result`(생성 안내) JSON으로 조회한다. 상세: [`docs/api/api-overview.md`](../docs/api/api-overview.md).

`auth` · `users` · `contracts` · `documents` · `extractions` · `analyses` · `results` · `checklists` · `feedback`

계약 연습은 실제 계약 건과 분리된 `practice-scenarios`·`practice-sessions` API를 사용한다. API 키가 있으면 Gemini practice provider, 키가 없고 `PRACTICE_OFFLINE_MODE=true`이면 승인 answer-key 기반 Fake provider를 선택한다. 실제 API 연결 검증 절차는 [`docs/testing/practice-real-api-validation.md`](../docs/testing/practice-real-api-validation.md)를 따른다.

## 컴포넌트 경계 (오케스트레이션 시 준수)

- **규칙 엔진 판정을 LLM·로컬 모델이 임의로 변경하지 못한다.** 규칙 결과가 최종 판정이다.
- **RAG 근거가 없어도** 규칙 엔진의 `RuleStatus`·`urgency`를 유지하고 `evidence_sources=[]`로 반환한다.
- 추출값과 생성값을 구분해 저장한다.
- 결과 상태 9개·시급도 5개는 루트 AGENTS.md를 단일 기준으로 참조한다. `안전`/`위험`/`점수` 같은 종합 판정은 사용하지 않는다.

## app/ 하위 구조

각 디렉터리의 세부 책임·입출력·TODO는 해당 디렉터리 README 참조.

```
app/
  main.py            FastAPI 진입점
  api/routes/        엔드포인트 (요청·응답, 입력 검증, 오류 형식)
  api/dependencies/  요청 의존성 주입 (인증 주체·DB 세션·검증)
  services/          목표 오케스트레이션 계층 + legacy minimum MVP 서비스
  repositories/      목표 저장소 경계 (현재 별도 구현 없음)
  schemas/           요청·응답 Pydantic 모델
  models/            구현된 SQLAlchemy 영속 모델
  core/              설정·공통 오류·보안 유틸
  workers/           분석 실행 등 비동기·백그라운드 작업
tests/               api/services/repositories 테스트
```

## 로컬 개발 DB (Docker PostgreSQL)

발표 전까지는 **각자 자기 컴퓨터에서 Docker DB를 켜고** 개발·확인한다. (MVP 완성 후 담당 B의 로컬 DB를 메인으로 전환하고 접속 주소를 공유할 예정 — 전환 방법은 그때 이 섹션에 추가)

사전 준비: Docker Desktop 설치·실행.

### 최초 1회 셋업과 선택적 개발 시드

```bash
docker compose up -d db           # 저장소 루트에서 — DB 컨테이너 시작
cd backend
copy .env.example .env            # Windows (macOS는 cp .env.example .env)
pip install -e .                  # 본인 파이썬 환경 활성화 후
python scripts/seed_dev.py        # DEV_SEED_* 3개가 있을 때만 계정 생성
```

`DEV_SEED_USERNAME`, `DEV_SEED_EMAIL`, `DEV_SEED_PASSWORD`를 모두 명시해야 시드가 생성된다. 비밀번호는 가입 API와 같은 규칙을 적용하며 로그에 출력하지 않는다. 값이 없으면 스크립트는 사용법만 안내하고 종료한다.

### 이후 매일 개발 시작할 때

```bash
docker compose up -d db           # 저장소 루트에서 — 이것만 실행
```

### "DB 구조가 바뀌었어요" 공지가 왔을 때 (그때만)

Alembic 도입 완료(2026-07-18). 초기화 없이 명령 한 줄로 구조를 반영한다:

```bash
cd backend
alembic upgrade head              # 스키마 변경 적용
```

- **기존에 쓰던 로컬 DB**(Alembic 도입 전부터 있던 DB)는 최초 1회만 `alembic stamp head`로 현재 상태를 기록한 뒤 위 명령을 쓴다.
- 스키마를 바꾸는 사람은 `app/models/` 수정 후 `alembic revision --autogenerate -m "설명"`으로 revision을 만들어 커밋한다. **revision은 동시에 여러 명이 만들면 head가 갈라진다** — 만들기 전에 팀에 공유.
- DB URL은 `alembic/env.py`가 `.env`의 `DATABASE_URL`에서 읽는다. 완전 초기화가 필요하면 기존 방식(`docker compose down -v` → `up` → seed)도 여전히 동작한다.

- 호스트 포트는 **5433**이다(로컬 설치 PostgreSQL의 5432와 충돌 방지). 접속 문자열은 `.env`의 `DATABASE_URL` 참조.
- 연결 확인이 필요하면 backend/에서 `python -m app.core.db` — "DB 연결 OK: ..."가 나오면 성공.
- 데이터는 Docker 볼륨(`pgdata`)에 남는다. `docker compose down`으로 꺼도 유지되고, 완전 초기화는 `docker compose down -v` (초기화 후엔 시드 스크립트 재실행).

## 저장하면 안 되는 파일

- AI 추출·규칙·RAG 로직 (→ `ai/`, 중복 구현 금지)
- 실제 개인정보·계약 문서, 업로드 원본, 모델 가중치
- API 키·비밀정보 (→ `.env`)

## 다른 폴더와의 연결

- `ai/` 패키지를 호출한다. AI 내부 로직을 재구현하지 않는다.
- `frontend/`와 API 스키마를 동기화한다. (`docs/api/`)

## 확정 vs 미정

**확정**

- FastAPI 사용, 계층 분리(API·의존성·서비스·저장소)
- 계약 건(`contract_id`) 단위 영속 저장 **필요**
- 데이터베이스: **PostgreSQL + SQLAlchemy** (2026-07-16, [`../docs/decisions/2026-07-16-mvp-platform-stack.md`](../docs/decisions/2026-07-16-mvp-platform-stack.md)) — 로컬 개발은 위 Docker 섹션 참조
- 인증: **JWT Bearer + bcrypt 계열 해시** (2026-07-16). 구현 라이브러리는 **PyJWT + Passlib-bcrypt** (팀 확정)
- 도메인 타입은 `ai/src/lease_companion_ai/schemas/` Pydantic 공통 타입 재사용 — 중복 정의 금지 ([`../docs/decisions/2026-07-16-shared-pydantic-schema.md`](../docs/decisions/2026-07-16-shared-pydantic-schema.md))
- backend가 AI 파이프라인 오케스트레이션·저장 담당

**미정 (TODO)**

- refresh token·토큰 폐기·서명 키 관리 (토큰 만료는 **24h 확정** — 2026-07-16)
- 운영용 외부 작업 큐·재시도·상태 전달 방식 (현재 로컬 MVP는 BackgroundTasks + HTTP 폴링)

## 현재 상태

- `main.py`(실서비스 진입점)와 `mvp_app.py`(최소 MVP 데모 앱 — 정적 UI + `/api/minimum-mvp/extract`·`/analyze` 라우트, `services/minimum_mvp.py` 경유 `ai/` 호출) 병존.
- **회원 API 구현 완료**: `POST /api/auth/signup` · `POST /api/auth/login` · `GET /api/auth/me` (PyJWT + Passlib-bcrypt). 오류 응답은 `{"error": {"code", "message"}}` 형식. 실행: `uvicorn app.main:app --reload` (backend/에서, DB 필요 — 위 Docker 섹션). 테스트: `python -m pytest tests`.
- **계약 건 API 구현 완료**: 생성·목록·상세·삭제 + 계약 상황 입력(`PUT /api/contracts/{id}/situation`). 본인 소유만 접근 가능(그 외 404). 경로 상세: [`../docs/api/api-overview.md`](../docs/api/api-overview.md).
- **문서 업로드 구현 완료**: `POST/GET /api/contracts/{id}/documents` (pdf·jpg·png 20MB 이하, 재업로드 이력 유지, 파일은 `UPLOAD_DIR`(기본 `backend/uploads/`, gitignore됨)에 저장) + 모의 등기 연결 `POST /api/contracts/{id}/registry-link`.
- **분석 결과 저장·재조회 구현 완료**: `POST/GET /api/contracts/{id}/analysis-runs` — 현재 로컬 MVP는 비동기 실행 후 폴링(status: pending/running/completed/failed). 운영 상태 전달 방식은 TODO. 최신 확인 완료 스냅샷으로 실행, `AnalysisRunResult`를 JSONB로 저장(재분석마다 새 행 = 이력). 계약 상황 입력도 통합 ContractContext 전체 필드(deposit_paid·signed·move_in_date·balance_payment_date·is_proxy_contract)로 확장.
- **추출 실행·확인·수정 API 구현 완료**: `POST …/extractions`(비동기, 업로드 문서 + 모의 등기 연결 기반) · `GET …/extractions/latest`(폴링) · `POST …/corrections`(원본 보존 + CorrectionRequest 이력) · `POST …/extractions/confirm`(서버 측 불변 InputSnapshot 생성). data-contract-v1 B 인수 체크리스트 5항목 전부 테스트로 충족.
- **체크리스트·계약 직후 행동 상태 API 구현 완료**: `GET /api/contracts/{id}/checklist-items`(?kind 필터) · `PUT …/checklist-items/{kind}/{item_key}`(`{done}` upsert). 항목 문구는 분석 결과가 원본 — 상태만 계약 건 단위 저장·재조회. 생성 항목 원본과 item_key 존재 검증은 후속 TODO.
- 백그라운드 실행은 FastAPI BackgroundTasks(`app/workers/analysis.py`) — 별도 워커 프로세스 분리는 LLM 파이프라인 장시간화 시. **기동 시 stale 실행 복구**(2026-07-17): 서버 재시작으로 pending/running에 멈춘 추출·분석·생성 실행을 failed로 정리해 클라이언트 무한 폴링을 방지한다(`fail_stale_runs`). 규칙 결과가 이미 저장된 행의 `result`·`status=completed`는 건드리지 않는다.
- **CASE-001 통합 시나리오 테스트**: `tests/api/test_case001_e2e.py` — 회원가입→로그인→계약 건→상황 입력→업로드+registry-link→추출→수정→확인→분석 폴링→체크리스트→**재로그인 후 재조회**까지 8단계 흐름 1건 (4단계 통합 검증의 백엔드 몫).
- **주의**: 기동 시 `create_all`은 새 테이블만 만들고 기존 테이블 컬럼 추가는 못 한다. 기존 테이블 변경은 Alembic revision으로 적용한다(위 "DB 구조가 바뀌었어요" 절 참조).
- **피드백 API 구현 완료**(2026-07-17): `POST/GET /api/contracts/{id}/feedback` — 자유 텍스트(1~2000자) + 선택 평점(1~5), 계약 건 단위 이력(수정·삭제 없음), 본인 소유만. 신규 테이블 `user_feedbacks`는 기동 시 `create_all`이 자동 생성.
- **계약 연습 API 구현 완료**(2026-07-22): 승인 시나리오 3개 목록·상세, 사용자별 세션 생성·복원, 현재 TURN 제출, 최종 행동, 결과 재조회 API. `practice_sessions`·`practice_turns`에 저장하며 answer-key·숨은 신호·미래 TURN은 응답하지 않는다.
- **classification 저장 준비**(2026-07-18): `analysis_runs`에 `classification_result` JSONB·`classification_error` TEXT 추가 (revision `c8b3bd1c03c6`). canonical `ClassificationResult` JSON을 provenance 포함 통째 저장하는 계약(BC_HANDOFF B 결정) — API 미노출, worker 연결은 A의 classification 실행 계층 완성 후.
- **Alembic 도입 완료**(2026-07-18): [`../docs/decisions/2026-07-17-alembic-migration.md`](../docs/decisions/2026-07-17-alembic-migration.md) 합의에 따라 `backend/alembic/` 구성. baseline revision `7adac2280b55`(현행 9개 테이블 전체), 기존 dev DB는 `stamp head`로 기록. 이후 스키마 변경은 revision으로만.
- **canonical v1.8.0 연결(2026-07-18)**: ① confirm이 계약 상황을 `ContractContext`로 스냅샷에 불변 포함 ② 분석 시작 시 현재 계약 상황과 다르면 422 `contract_context_changed` ③ 워커가 R01~R10과 J01~J12 전체 결과를 저장 ④ 같은 snapshot의 ContractContext를 GenerationService에 전달해 `StageGuidance`와 `prompt_version`을 생성·검증·분리 저장 ⑤ `GenerationResult`가 R `items`와 J `judgment_items`를 분리하고 안정 `item_key`를 저장 ⑥ 생성 실패 시 규칙 결과를 유지한다.
