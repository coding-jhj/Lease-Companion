# 슬기로운 계약생활 (lease-companion)

첫 전월세 계약을 준비하는 **2030 청년 임차인**을 위한 계약 확인 도우미. 회원 기반 모바일 웹앱에서 사용자가 계약 건과 계약 문서를 관리하고, AI·규칙 엔진·RAG가 확인 항목·질문·행동을 근거와 함께 제공한다.

> AI는 계약 가능·안전·전세사기·법률적 결론을 **단정하지 않는다.** 사용자가 직접 확인할 항목·질문·체크리스트·증빙 행동을 제공한다.

## 대상 사용자

- 첫 전월세 계약을 준비하는 2030 청년 임차인
- 대상 계약: 주거용 전세 / 보증부 월세 / 일반 월세

## 해결하려는 문제

첫 계약자는 계약서·특약·등기의 무엇을 확인해야 하는지, 어떤 질문을 해야 하는지, 계약 직후 무슨 권리를 확보해야 하는지 모른다. 정보는 흩어져 있고 판단은 어렵다.

## 최신 MVP

회원 기반 모바일 웹앱에서 사용자가 계약 건과 계약 문서를 관리하고, 상용 LLM(Gemini 3.5 Flash)이 임대차 조항 유형과 불명확성 후보를 구조화한다. Python 규칙 엔진은 계약서와 관련 문서의 값을 교차검증하고, 공식자료 RAG와 상용 LLM(Gemini 3.5 Flash)은 판정 근거·쉬운 설명·확인 질문·사용자 행동을 생성한다. 파인튜닝한 로컬 7B는 상용 대비 성능비교 병렬 실험(선택)으로만 유지하며 MVP 크리티컬 패스에서 제외한다.

## 핵심 기능

- 회원가입·로그인·로그아웃·회원 탈퇴
- 사용자별 계약 건 생성·조회·삭제
- 계약 단계·계약 상황 입력
- 계약서·특약 필수 업로드 / 등기사항증명서·중개대상물 확인설명서 선택 업로드
- 디지털 PDF 텍스트 추출(PyMuPDF·PDF.js), 스캔 PDF·사진 OCR(상용 LLM Gemini 3.5 Flash VLM 통합 — 표·체크박스·레이아웃 포함)
- 핵심 정보 구조화 + 사용자 추출값 확인·수정
- 상용 LLM(Gemini 3.5 Flash) 기반 조항 유형·명확성 후보 구조화 (로컬 7B는 선택적 성능비교 실험 — MVP 크리티컬 패스 제외)
- Python 규칙 엔진 문서 내부 판정과 문서 교차검증
- 공식 법령·공공자료 RAG
- 상용 LLM 기반 쉬운 설명·질문·행동 생성 및 저신뢰 결과 재검토
- 판정·원문 증거·공식 근거·질문·행동 리포트
- 결과 저장·재조회, 서명 전 체크리스트 상태 저장, 계약 직후 행동 상태 저장
- 추출·판정·근거 오류 사용자 피드백

## 사용자 흐름 (8단계)

1. 회원가입·로그인
2. 계약 대시보드·계약 건 생성
3. 계약 상황 입력
4. 계약서·등기 등 문서 업로드
5. 추출값 확인·수정
6. 상용 LLM 구조화(Gemini 3.5 Flash)·규칙 엔진·RAG·상용 LLM 분석
7. 판정·원문 증거·공식 근거·질문·행동 리포트
8. 저장된 체크리스트·계약 직후 행동 관리

추출값은 분석(6단계) 전에 사용자가 확인·수정할 수 있다. 분석 결과·체크리스트는 계약 건 단위로 저장·재조회한다. 상세: [docs/planning/user-flow.md](docs/planning/user-flow.md)

## PoC와 MVP

PoC와 MVP는 서로 다른 기능 목록이 아니다. **PoC는 기술 검증 단계**, **MVP는 검증된 기술을 통합한 실제 사용자 서비스**다.

- **PoC**: 샘플 계약서·등기 입력 → PDF·OCR 처리(디지털 PyMuPDF·PDF.js / 스캔·사진 Gemini 3.5 Flash VLM) → 추출·정규화 → 상용 LLM 구조화(Gemini 3.5 Flash, 로컬 7B는 선택적 성능비교) → 핵심 판정 6개 → 규칙 교차검증 → RAG → 구조화 JSON → 모델 비교평가. 상세: [docs/planning/poc-scope.md](docs/planning/poc-scope.md)
- **MVP**: 회원·계약 건·업로드·확인 수정·12개 판정·등기 교차검증·근거·질문·행동 리포트·저장 재조회·체크리스트·계약 직후 행동 상태 관리. 상세: [docs/planning/mvp-scope.md](docs/planning/mvp-scope.md)

## 전체 시스템 구성

```
frontend (모바일 웹앱)
   ↓
backend (FastAPI: 회원·계약 건·문서·분석·결과 오케스트레이션 + 저장)
   ↓
ai 파이프라인
  문서 입력 → 디지털 PDF 추출(PyMuPDF·PDF.js)·OCR(Gemini 3.5 Flash VLM 통합) → 필드 추출 → (사용자 확인·수정)
  → 상용 LLM 구조화·불명확성 후보(Gemini 3.5 Flash) → Python 규칙 엔진 판정·교차검증
  → RAG 공식 근거 → 저신뢰 결과 상용 LLM 재검토 → 설명·질문·체크리스트·행동 생성
  → guardrail → 저장
        ↑
     data (샘플·스키마·규칙·라벨·데이터셋·RAG 자료·평가·모델 메타데이터)
```

상세: [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md), [docs/architecture/ai-pipeline.md](docs/architecture/ai-pipeline.md)

## 폴더별 책임

| 폴더 | 책임 |
|------|------|
| [`ai/`](ai/README.md) | 문서 인식·추출·정규화·상용 LLM 구조화·규칙 엔진·RAG·생성·guardrail·routing·평가·로컬 7B 파인튜닝(선택 실험) |
| [`backend/`](backend/README.md) | FastAPI. 회원·계약 건·문서·분석·결과 API, 오케스트레이션·저장 |
| [`frontend/`](frontend/README.md) | 회원·계약 관리 포함 모바일 웹앱 (React + Vite + TypeScript — 2026-07-16 확정) |
| [`data/`](data/README.md) | 비식별·합성 샘플, 스키마, 규칙, 라벨, 데이터셋, RAG 자료, 평가, 모델 메타데이터 |
| [`docs/`](docs/README.md) | 기획·아키텍처·API·데이터·AI·백엔드 설계, 결정 기록, 회의록 |

## 기술 방향

**확정 (방향)**

- AI: Python. Backend: Python + FastAPI
- 문서 처리: 디지털 PDF 텍스트 추출(PyMuPDF·PDF.js) + OCR(상용 LLM Gemini 3.5 Flash VLM 통합, 스캔·사진). PaddleOCR-VL은 (선택) 비교실험
- 조항 유형·명확성 후보 구조화: 상용 LLM(Gemini 3.5 Flash). 파인튜닝한 로컬 7B(QLoRA)는 상용 대비 선택적 성능비교 실험 — MVP 크리티컬 패스 제외
- 문서 내부 판정·교차검증: Python 규칙 엔진 (최종 판정)
- 근거 검색: 공식 자료 기반 RAG (gemini-embedding-001 + BM25, Cohere rerank-v4.0-pro)
- 설명·질문·행동 생성 및 저신뢰 재검토: 상용 LLM(Gemini 3.5 Flash)
- 회원 기반 서비스 + 계약 건 단위 영속 저장

**확정 (2026-07-16 플랫폼 스택 — [docs/decisions/2026-07-16-mvp-platform-stack.md](docs/decisions/2026-07-16-mvp-platform-stack.md))**

- 데이터베이스: PostgreSQL
- 인증: JWT Bearer, PyJWT + Passlib-bcrypt (Access Token 24시간은 로컬 MVP 임시값)
- 프론트엔드: React + Vite + TypeScript
- 벡터 데이터베이스: Chroma 로컬 모드
- 통합 스키마: `ai/src/lease_companion_ai/schemas/` Pydantic 단일 원본 ([docs/decisions/2026-07-16-shared-pydantic-schema.md](docs/decisions/2026-07-16-shared-pydantic-schema.md))
- 현재 MVP는 로컬 실행

**미정 (TODO — 임의 확정·설치 금지)**

- 운영 배포 플랫폼 (로컬 실행은 운영 배포 확정이 아님)
- refresh token·토큰 폐기·운영 서명 키 관리와 운영용 토큰 만료 정책
- 로컬 7B 베이스 모델 (상용 대비 선택적 성능비교 실험 — 베이스 미정)

## 로컬 실행 (전체 MVP)

회원가입부터 계약 건 저장, 문서 업로드, 추출값 확인·수정, 분석 리포트와 체크리스트 재조회까지 실행하는 기본 경로다. Windows PowerShell 기준이며 다음 프로그램이 필요하다.

- Python 3.10
- Node.js 20.19 이상 또는 22.12 이상과 npm
- Docker Desktop

### 1. 최초 1회 설치

저장소 루트에서 Python 가상환경과 백엔드·AI 의존성을 설치한다.

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .\ai -e .\backend

if (-not (Test-Path backend\.env)) {
    Copy-Item backend\.env.example backend\.env
}

cd frontend
npm install
cd ..
```

PowerShell이 가상환경 스크립트 실행을 막으면 현재 터미널에서 `Set-ExecutionPolicy -Scope Process Bypass`를 한 번 실행한 뒤 다시 활성화한다. `backend/.env`의 개발용 DB 주소와 JWT 키는 Docker 로컬 실행에 바로 사용할 수 있는 예시값이다. 실제 비밀값은 Git에 커밋하지 않는다.

Gemini·Cohere 실호출은 선택 사항이다. 사용하려면 `backend/.env`에 `GEMINI_API_KEY`와 `COHERE_API_KEY`를 설정한다. 키가 없으면 디지털 PDF/TXT 추출, 정규식 구조화 폴백, 로컬 BM25 근거 검색과 안전 생성 폴백으로 동작한다. 스캔·사진 PDF의 OCR에는 `GEMINI_API_KEY`가 필요하다.

### 2. PostgreSQL 시작과 마이그레이션

Docker Desktop을 실행한 뒤 저장소 루트에서 실행한다. PostgreSQL은 로컬 `5432`와 겹치지 않도록 `5433` 포트를 사용한다.

```powershell
docker compose up -d db

cd backend
..\.venv\Scripts\Activate.ps1
alembic upgrade head
```

DB 연결을 확인하려면 같은 `backend` 터미널에서 `python -m app.core.db`를 실행한다.

### 3. 백엔드 실행 (터미널 1)

```powershell
cd backend
..\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`http://127.0.0.1:8000/health`에서 `{"status":"ok"}`가 나오면 준비된 상태다. API 문서는 `http://127.0.0.1:8000/docs`에서 확인한다.

### 4. 프론트엔드 실행 (터미널 2)

```powershell
cd frontend
npm run dev
```

브라우저에서 `http://127.0.0.1:5173`에 접속한다. 기본 개발 모드는 MSW가 아니라 `http://127.0.0.1:8000`의 실제 백엔드 API를 사용한다.

개발 확인용 문서는 다음 합성 샘플을 사용할 수 있다.

- 계약서: `data/sample/contracts/contract_001.txt`
- 등기사항증명서: `data/sample/registry-records/registry_001.txt`

서버는 각 터미널에서 `Ctrl+C`로 종료하고 DB는 저장소 루트에서 `docker compose down`으로 중지한다. 이 명령은 DB 데이터를 보존한다.

### DB 없이 빠르게 데모만 실행

회원·계약 건 저장이 필요 없는 단일 서버 데모는 저장소 루트에서 다음과 같이 실행한다.

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-minimum-mvp.txt
.\scripts\run-minimum-mvp.ps1
```

브라우저에서 `http://127.0.0.1:8000`에 접속한다. 이 경로는 정식 React 프론트엔드와 PostgreSQL 영속 저장을 포함하지 않는다. 상세 범위와 제한사항은 [`docs/planning/minimum-mvp-runbook.md`](docs/planning/minimum-mvp-runbook.md)를 참고한다.

## 데이터 / 개인정보 보호 원칙

- 실제 계약서·개인정보·모델 가중치·체크포인트를 Git에 커밋하지 않는다.
- `data/sample`·`data/datasets`에는 가상 또는 완전 비식별화 데이터만 둔다.
- 이름·주소·연락처·계좌번호 등 민감정보 커밋 금지.
- RAG 자료는 공식 법령·표준계약서·공공기관 자료를 우선한다.
- 상세: [docs/data/privacy-policy.md](docs/data/privacy-policy.md)

## 현재 프로젝트 상태

- **실전 계약 점검**: 회원가입부터 계약 생성, 문서 업로드, 추출값 확인·수정, R01~R24·J01~J12 분석, DP01~DP08 비교, 특약별 공식 근거·질문·수정 요청·행동 안내, PDF, 체크리스트 저장·재조회까지 Backend·Frontend에 연결됐다.
- **특약 RAG**: 6개 특약 유형의 결정적 매칭, 공식 source·section 검색, 생성·Guardrail, Backend 저장, Frontend 카드·PDF가 연결됐다. 오프라인 잠금 평가에서 카탈로그 `30/30`, source Top-3 `13/15`, section Top-3 `10/15`, 금지 단정 `0`을 기록했다. 독립 검토와 실제 Gemini·Cohere 품질 검증은 미완료다.
- **계약 연습**: 조건부 보증금 반환, 제3자 계좌 송금, 대리인 권한 미확인 3개 합성 시나리오가 AI 답변 평가, Backend 세션·턴·결과 저장, Frontend 텍스트 대화·복기와 연결됐다. 미디어·음성은 후속 범위다.
- **검증 경계**: 실제 FastAPI·PostgreSQL 브라우저 E2E와 API 키 없는 fallback 흐름은 검증 기록이 있다. 실제 Gemini·Cohere 네트워크 응답 품질·비용은 아직 검증하지 않았다.
- **현재 제한**: R20~R22 외부 데이터 자동 연결, 운영 배포·보안 정책, 실제 provider 품질 평가, 독립 평가셋 검토는 후속이다.

실행 기준은 위 로컬 실행 절, [`docs/planning/minimum-mvp-runbook.md`](docs/planning/minimum-mvp-runbook.md), [`docs/testing/practice-real-api-validation.md`](docs/testing/practice-real-api-validation.md)를 따른다.
