# backend/

슬기로운 계약생활의 API 서버. **FastAPI** (Python).

## 목적

로그인한 사용자의 **계약 건(ContractProject)** 단위로 문서·추출값·분석 실행·결과를 관리한다.
분석은 단일 세션으로 끝나지 않고 계약 건 단위로 **영속 저장·재조회**된다. backend는
프론트엔드 요청을 받아 입력·업로드 파일을 검증하고, `ai/` 파이프라인(상용 LLM 구조화 →
규칙 엔진 → RAG → 상용 LLM 생성, 로컬 7B는 선택적 성능비교 실험)을 **오케스트레이션**하며,
판정·근거·질문·행동·체크리스트를 저장한다.

## 담당 기능

- 회원가입·로그인 (JWT Bearer + bcrypt 계열 — 구체 라이브러리·토큰 정책 TODO)
- 계약 대시보드·계약 건 생성·조회
- 계약 상황 입력
- 계약서·등기 등 문서 업로드, 형식·크기·개수 검증
- 추출값 확인·수정 반영
- 분석 실행(상용 LLM 구조화 → 규칙 엔진 → RAG → 상용 LLM 생성, 로컬 7B는 선택적 성능비교 실험) 오케스트레이션
- 분석 상태 관리 (분석 중/완료/오류)
- 판정·원문 증거·공식 근거·질문·행동 리포트 저장·조회
- 체크리스트·계약 직후 행동 상태 관리
- 사용자 피드백 수집
- 공통 오류 처리

## 도메인 엔터티

루트 [`../AGENTS.md`](../AGENTS.md)와 [`docs/backend/auth-and-persistence.md`](../docs/backend/auth-and-persistence.md) 기준.

`User` · `ContractProject` · `Document` · `ExtractedField` · `AnalysisRun` · `JudgmentResult` · `EvidenceSource` · `QuestionCard` · `ChecklistItem` · `PostContractAction` · `UserFeedback`

> `AnalysisRun`을 표준 명칭으로 사용한다. (루트 AGENTS.md의 `AnalysisJob`은 동의 표기)

## API 책임 영역

경로·메서드·스키마는 미확정(`TODO`). 상세: [`docs/api/api-overview.md`](../docs/api/api-overview.md).

`auth` · `users` · `contracts` · `documents` · `extractions` · `analyses` · `results` · `checklists` · `feedback`

## 컴포넌트 경계 (오케스트레이션 시 준수)

- **규칙 엔진 판정을 LLM·로컬 모델이 임의로 변경하지 못한다.** 규칙 결과가 최종 판정이다.
- **RAG 근거가 없으면** `확인 불가` 또는 `확인 필요`로 반환한다. RAG는 판정하지 않는다.
- 추출값과 생성값을 구분해 저장한다.
- 결과 상태 9개·시급도 5개는 루트 AGENTS.md를 단일 기준으로 참조한다. `안전`/`위험`/`점수` 같은 종합 판정은 사용하지 않는다.

## app/ 하위 구조

각 디렉터리의 세부 책임·입출력·TODO는 해당 디렉터리 README 참조.

```
app/
  main.py            FastAPI 진입점
  api/routes/        엔드포인트 (요청·응답, 입력 검증, 오류 형식)
  api/dependencies/  요청 의존성 주입 (인증 주체·DB 세션·검증)
  services/          계약 건·분석 실행 흐름 오케스트레이션 (ai/ 호출)
  repositories/      도메인 엔터티 영속화 (DB 확정 전 경계)
  schemas/           요청·응답 Pydantic 모델
  models/            도메인/영속 모델 (DB 확정 후)
  core/              설정·공통 오류·보안 유틸
  workers/           분석 실행 등 비동기·백그라운드 작업
tests/               api/services/repositories 테스트
```

## 로컬 개발 DB (Docker PostgreSQL)

발표 전까지는 **각자 자기 컴퓨터에서 Docker DB를 켜고** 개발·확인한다. (MVP 완성 후 담당 B의 로컬 DB를 메인으로 전환하고 접속 주소를 공유할 예정 — 전환 방법은 그때 이 섹션에 추가)

사전 준비: Docker Desktop 설치·실행.

### 최초 1회 셋업 (이걸 해야 admin 계정이 생성된다)

```bash
docker compose up -d db           # 저장소 루트에서 — DB 컨테이너 시작
cd backend
copy .env.example .env            # Windows (macOS는 cp .env.example .env)
pip install -e .                  # 본인 파이썬 환경 활성화 후
python scripts/seed_dev.py        # → admin / 1234 계정 생성
```

### 개발용 테스트 계정 (로그인 시 사용)

| 항목 | 값 |
|---|---|
| ID | `admin` |
| PW | `1234` |

가입 API의 비밀번호 규칙을 우회해 DB에 직접 생성한 계정이다 — **로컬 개발 DB 전용**, 메인 서버 전환 후에는 `seed_dev.py`를 실행하지 않는다.

### 이후 매일 개발 시작할 때

```bash
docker compose up -d db           # 저장소 루트에서 — 이것만 실행
```

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
- 회원 외 영역(`contracts` 이후)의 구체 API 경로·메서드·요청/응답 스키마 (`registry-link` 전체 경로 포함)
- 비동기 분석 상태 전달 방식(폴링 vs 콜백)
- FastAPI 의존성 확정 후 `pyproject.toml` 갱신
- 실행 명령(예: uvicorn) 확정 후 이 README에 기록

## 현재 상태

- `main.py`(실서비스 진입점)와 `mvp_app.py`(최소 MVP 데모 앱 — 정적 UI + `/api/minimum-mvp/extract`·`/analyze` 라우트, `services/minimum_mvp.py` 경유 `ai/` 호출) 병존.
- **회원 API 구현 완료**: `POST /api/auth/signup` · `POST /api/auth/login` · `GET /api/auth/me` (PyJWT + Passlib-bcrypt). 오류 응답은 `{"error": {"code", "message"}}` 형식. 실행: `uvicorn app.main:app --reload` (backend/에서, DB 필요 — 위 Docker 섹션). 테스트: `python -m pytest tests/api/test_auth.py`.
- 계약 건 영속 저장·저장소·워커는 미구현.
