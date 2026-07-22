# 계약 연습 실제 API 검증 방법

이 문서는 계약 연습 시나리오 3개가 모의 브라우저 API가 아니라 실제 Frontend·FastAPI·PostgreSQL·AI Fake provider를 통해 끝까지 연결되는지 확인하는 개발자용 실행 절차입니다.

## 1. 무엇을 검증하는가

```text
브라우저
  ↓ 실제 fetch
Vite /api proxy
  ↓
FastAPI Practice API
  ↓
PostgreSQL practice_sessions·practice_turns
  ↓
PracticeSimulationService
  ↓
FakePracticeProvider
  ↓
저장된 세션·턴·최종 복기
  ↓
Frontend 결과 화면
```

이 검증은 실제 애플리케이션 연결을 확인하지만 Gemini 네트워크를 호출하지 않습니다. `GEMINI_API_KEY`를 비우고 `PRACTICE_OFFLINE_MODE=true`로 실행합니다.

## 2. 현재 자동화 상태

| 항목 | 현재 상태 |
|---|---|
| Practice AI·Backend 테스트 | 완료 |
| Practice Frontend·MSW 테스트 | 완료 |
| 실제 API용 Playwright 설정 | `frontend/playwright.real-api.config.ts` 존재 |
| Practice 실제 API E2E 파일 | **미구현** — `frontend/e2e/practice-flow.spec.ts` 없음 |
| 실제 Gemini smoke | 기본 skip, 이번 검증 범위 제외 |

따라서 현재는 아래 수동 절차로 실제 연결을 확인할 수 있습니다. 자동 검증은 작업 9에서 `practice-flow.spec.ts`를 만든 뒤 실행합니다.

## 3. 사전 준비

- Python `3.10`
- Docker Desktop 실행
- Node.js와 npm
- Playwright 자동 검증을 할 경우 Chromium 설치

저장소 루트 `C:\Lease-Companion`에서 처음 한 번만 의존성을 설치합니다.

```powershell
python -m pip install -e .\ai
python -m pip install -e .\backend
Set-Location frontend
npm ci
npx playwright install chromium
```

Playwright를 실행하지 않고 수동 브라우저 확인만 할 경우 마지막 명령은 생략할 수 있습니다.

## 4. Backend 환경 설정

`backend/.env`가 없다면 저장소 루트에서 예시 파일을 복사합니다.

```powershell
Copy-Item backend\.env.example backend\.env
```

이미 `.env`가 있으면 덮어쓰지 말고 다음 항목만 확인합니다. 실제 값은 Git에 커밋하지 않습니다.

```dotenv
DATABASE_URL=postgresql+psycopg://lease:lease_dev_only@localhost:5433/lease_companion
JWT_SECRET=로컬에서만_사용할_32바이트_이상_비밀값
GEMINI_API_KEY=
PRACTICE_OFFLINE_MODE=true
```

Provider 선택 규칙:

| `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY` | `PRACTICE_OFFLINE_MODE` | 선택 결과 |
|---|---|---|
| 있음 | 값과 무관 | Gemini provider |
| 없음 | `true` | Fake provider |
| 없음 | `false` | Provider 없음, `needs_review` fallback |

실제 API 연결만 검증할 때는 반드시 두 키를 모두 비우고 offline mode를 `true`로 둡니다. 운영체제 환경 변수에 키가 저장돼 있을 수 있으므로 FastAPI를 실행할 같은 터미널에서 다음 명령도 사용합니다.

```powershell
Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:GOOGLE_API_KEY -ErrorAction SilentlyContinue
```

## 5. 서버 실행

### 터미널 1 — PostgreSQL

저장소 루트에서 실행합니다.

```powershell
docker compose up -d db
```

데이터를 삭제하는 `docker compose down -v`는 이 검증에 필요하지 않습니다.

### 터미널 2 — FastAPI

`backend/.env`를 올바르게 읽도록 `backend` 폴더에서 실행합니다.

```powershell
Set-Location C:\Lease-Companion\backend
Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:GOOGLE_API_KEY -ErrorAction SilentlyContinue
alembic upgrade head
python -m app.core.db
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

준비 완료 기준:

- DB 확인 명령에 `DB 연결 OK`가 표시됩니다.
- FastAPI가 `http://127.0.0.1:8000`에서 대기합니다.

### 터미널 3 — Frontend

MSW 환경 변수를 제거하고 실제 API 모드로 실행합니다.

```powershell
Set-Location C:\Lease-Companion\frontend
Remove-Item Env:VITE_ENABLE_MSW -ErrorAction SilentlyContinue
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

`frontend/vite.config.ts`가 `/api` 요청을 `http://127.0.0.1:8000`으로 전달합니다.

## 6. 수동 검증 절차

브라우저에서 `http://127.0.0.1:5173/signup`을 엽니다.

### 공통 준비

1. 중복되지 않는 테스트 계정으로 회원가입합니다.
2. 로그인합니다.
3. 대시보드에서 `가상 계약 대화 연습`을 선택합니다.
4. 목록에 다음 세 시나리오가 모두 있는지 확인합니다.

| 시나리오 ID | 화면 제목 |
|---|---|
| `PRACTICE-DEFERRED-REFUND-001` | 후임 임차인 조건부 보증금 반환 |
| `PRACTICE-THIRD-PARTY-PAYMENT-001` | 공인중개사 명의 계좌로 가계약금 송금 요구 |
| `PRACTICE-PROXY-AUTHORITY-001` | 대리인 권한 자료 없는 계약 요구 |

### 시나리오별 확인

세 시나리오를 각각 다음 순서로 진행합니다.

1. 카드에서 `상황 먼저 보기`를 선택합니다.
2. `가상 연습`·`합성 시나리오` 라벨과 계약 상황·특약을 확인합니다.
3. `대화 연습 시작`을 선택합니다.
4. 현재 TURN에 맞는 답변을 입력합니다. 결정적 Fake 평가가 필요하면 해당 시나리오의 `answer-key.json`에서 현재 TURN의 `appropriate_check` 예시 하나를 사용합니다.
5. TURN이 `TURN-01 → TURN-02 → TURN-03 → ACTION-SELECTION` 순서로 진행되는지 확인합니다.
6. 최종 행동에서 `보류`를 선택합니다.
7. 결과 화면에 선택 행동, 확인한 행동, 놓친 신호, 권장 문구, 다음 행동, 공식자료 ID가 표시되는지 확인합니다.
8. 결과 화면을 새로고침해 같은 결과가 다시 표시되는지 확인합니다.

세션 복원은 한 시나리오에서 추가로 확인합니다.

1. `TURN-02` 또는 `TURN-03`에서 브라우저를 새로고침합니다.
2. 새로운 세션이 생성되지 않고 같은 `sessionId`와 현재 TURN이 복원되는지 확인합니다.

## 7. 실제 API를 사용했다는 증거

브라우저 개발자 도구의 Network에서 다음 요청을 확인합니다.

```text
GET  /api/practice-scenarios
GET  /api/practice-scenarios/{scenario_id}
POST /api/practice-sessions
GET  /api/practice-sessions/{session_id}
POST /api/practice-sessions/{session_id}/turns
POST /api/practice-sessions/{session_id}/final-action
GET  /api/practice-sessions/{session_id}/result
```

추가 확인:

- 응답이 MSW service worker에서 만들어지지 않았는지 확인합니다.
- Backend 터미널에 Practice API 요청이 기록되는지 확인합니다.
- 새로고침 후 같은 세션과 결과가 PostgreSQL에서 재조회되는지 확인합니다.
- `GEMINI_API_KEY`가 비어 있어 외부 Gemini 호출이 발생하지 않았는지 확인합니다.

## 8. 자동 Playwright 검증

현재 `frontend/e2e/practice-flow.spec.ts`가 없으므로 아래 명령은 아직 실행할 수 없습니다. 작업 9에서 전용 테스트를 먼저 구현해야 합니다.

전용 테스트가 준비된 뒤에는 PostgreSQL·Backend·Frontend를 앞 절과 같이 직접 실행한 상태에서 다음 명령을 사용합니다.

```powershell
Set-Location C:\Lease-Companion\frontend
npm run test:e2e:real -- e2e/practice-flow.spec.ts
```

`playwright.real-api.config.ts`는 서버를 자동으로 시작하지 않습니다. 다음 세 프로세스가 먼저 실행 중이어야 합니다.

1. PostgreSQL `localhost:5433`
2. FastAPI `127.0.0.1:8000`
3. MSW가 꺼진 Vite `127.0.0.1:5173`

전용 E2E에는 다음 행렬이 필요합니다.

| 확인 항목 | S1 | S2 | S3 |
|---|---:|---:|---:|
| 목록·상황 | 통과 | 통과 | 통과 |
| 세션 생성 | 통과 | 통과 | 통과 |
| 3개 TURN 진행 | 통과 | 통과 | 통과 |
| 미응답·재시도 | 통과 | 통과 | 통과 |
| 최종 행동 | 통과 | 통과 | 통과 |
| 복기 저장·새로고침 | 통과 | 통과 | 통과 |

Playwright 설정은 320×720, 360×800, 1440×900 세 viewport를 사용합니다.

## 9. 완료 판정

다음 조건을 모두 만족해야 실제 연결 검증 완료입니다.

- 세 시나리오가 실제 FastAPI에서 3/3 끝까지 진행됩니다.
- 현재 TURN만 Frontend에 전달되고 숨은 정답·미래 TURN은 노출되지 않습니다.
- 세션·턴·결과가 PostgreSQL에 저장되고 새로고침 후 복원됩니다.
- 중복 제출·잘못된 TURN·완료 후 추가 입력을 Backend가 거부합니다.
- 모바일 두 크기와 PC 화면에서 주요 조작을 완료할 수 있습니다.
- Fake provider만 사용하며 Gemini 네트워크 호출은 0회입니다.

## 10. 실제 Gemini 검증과의 차이

실제 Frontend↔Backend 검증과 Gemini live smoke는 다른 작업입니다.

| 검증 | 목적 | 외부 비용 |
|---|---|---|
| 실제 API + Fake provider | Frontend·FastAPI·DB·AI 상태 머신 연결 확인 | 없음 |
| Gemini live smoke | 실제 모델 인증·응답 형식·품질 확인 | 발생 가능 |

Gemini live smoke는 API 키 사용과 비용 승인을 받은 뒤 별도로 실행합니다. 이 문서의 절차에는 포함하지 않습니다.
