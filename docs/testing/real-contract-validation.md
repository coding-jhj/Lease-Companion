# 실전 계약 점검 로컬 실검증

이 문서는 MSW가 아닌 실제 FastAPI·PostgreSQL 경로에서 실전 계약 점검 흐름을 직접 확인하는 방법을 설명한다.

## 검증 범위

기본 실검증은 다음 경계를 확인한다.

`회원가입 → 로그인 → 계약 생성 → 문서 업로드 → 추출값 확인·수정 → 분석 → 리포트 → 체크리스트 저장·재조회`

- 실제 구성: React/Vite → FastAPI → PostgreSQL
- 기본 검색·생성: API 키가 없으면 로컬 BM25와 안전 fallback
- 실제 Gemini: `backend/.env`에 `GEMINI_API_KEY`가 있을 때만 사용
- 실제 Cohere rerank: `backend/.env`에 `COHERE_API_KEY`가 있을 때만 사용
- 스캔·사진 PDF OCR: Gemini 키가 있어야 검증 가능

실제 계약서나 개인정보가 포함된 문서는 저장소에 복사하거나 Git에 추가하지 않는다.

## 1. 최초 1회 준비

필수 프로그램은 Python 3.10, Node.js 20.19 이상 또는 22.12 이상, npm, Docker Desktop이다.

저장소 루트의 Windows PowerShell에서 실행한다.

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .\ai -e .\backend

if (-not (Test-Path backend\.env)) {
    Copy-Item backend\.env.example backend\.env
}

Set-Location frontend
npm install
npx playwright install chromium
Set-Location ..
```

이미 `.venv`, `backend/.env`, `frontend/node_modules`가 있으면 해당 준비는 다시 할 필요가 없다.

## 2. 수동 실검증 실행

Docker Desktop을 켠 뒤 저장소 루트에서 실행한다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -RealContractValidation
```

스크립트는 다음을 수행한다.

1. 저장소 `.venv`의 Python과 uvicorn 확인
2. PostgreSQL 컨테이너 시작
3. Alembic migration 적용
4. FastAPI를 `127.0.0.1:8301`에서 시작
5. Vite를 `127.0.0.1:5173`에서 시작
6. MSW를 끄고 회원가입 화면 열기

검증이 끝나면 실행 터미널에서 `Ctrl+C`를 누른다. Backend와 Frontend는 함께 종료되며 PostgreSQL 데이터는 보존된다.

## 3. 화면에서 확인할 순서

1. 테스트용 계정으로 회원가입하고 로그인한다.
2. `실전 계약 점검`을 선택한다.
3. `계약서 초안을 받았어요`를 선택하고 계약 상황을 입력한다.
4. 비식별 테스트 문서를 업로드한다.
5. 추출값을 항목별로 확인하고 필요한 값은 수정한다.
6. 분석을 시작하고 완료될 때까지 기다린다.
7. 리포트의 확인 우선순위, 원문 증거, 공식 근거, 질문, 행동 안내를 확인한다.
8. 체크리스트 상태를 변경하고 새로고침 후에도 유지되는지 확인한다.
9. 대시보드로 돌아가 계약과 분석 이력이 재조회되는지 확인한다.

API 상태는 `http://127.0.0.1:8301/health`, API 문서는 `http://127.0.0.1:8301/docs`에서 확인한다.

## 4. 자동 브라우저 실검증

수동 검증 서버가 실행 중인 상태에서 새 PowerShell을 열어 실행한다.

```powershell
Set-Location frontend
npm run test:e2e:real -- e2e/full-user-flow.spec.ts
```

이 검증은 모바일 320px, 모바일 360px, 데스크톱 1440px에서 실제 API 사용자 흐름을 실행한다. E2E에 포함된 문서는 합성 PDF이며 실제 개인정보를 사용하지 않는다.

## 5. 실제 Gemini·Cohere까지 검증

`backend/.env`에 본인의 키를 입력한 뒤 같은 명령을 다시 실행한다.

```dotenv
GEMINI_API_KEY=본인_키
COHERE_API_KEY=본인_키
```

키가 설정된 상태에서는 호출 비용과 외부 전송이 발생할 수 있다. 처음에는 개인정보가 없는 합성·비식별 문서만 사용한다. 키를 채팅, 로그, 스크린샷, Git에 남기지 않는다.

Gemini만 설정하면 OCR·구조화·생성·embedding의 실제 provider 경로를 확인할 수 있다. Cohere가 없으면 rerank는 로컬 경로로 fallback한다.

## 문제 해결

- Docker 오류: Docker Desktop이 완전히 실행된 뒤 다시 시도한다.
- 8301 또는 5173 포트 사용 중: 기존 개발 서버를 종료하거나, 본인이 실행한 서버만 확실한 경우 `-Force`를 사용한다.
- migration 충돌: DB 데이터를 지우거나 Alembic history를 임의 변경하지 말고 오류 전문을 확인한다.
- 스캔 PDF에서 추출 실패: `GEMINI_API_KEY` 설정 여부를 확인한다.
- 실제 API 여부 확인: 브라우저 Network에서 `/api/...` 요청이 발생하는지 확인한다. 이 모드는 `VITE_ENABLE_MSW`를 비워 실행한다.
