# 슬기로운 계약생활

> 첫 전월세 계약을 준비하는 청년을 위한 계약 확인 도우미

**🏆 K-디지털 트레이닝 해커톤 장려상(고용노동부장관상) 수상** — 2026.09, 상금 100만 원

계약서와 관련 문서를 함께 확인하고, 사용자가 **무엇을 확인하고·무엇을 묻고·어떤 기록을 남겨야 하는지** 근거와 함께 안내하는 회원 기반 모바일 웹앱입니다.

> [!IMPORTANT]
> 계약의 안전성·전세사기·적법성을 단정하지 않습니다. 확인 항목, 질문, 체크리스트, 증빙 행동을 제공합니다.

## 핵심 기능

- 계약 건 생성과 계약 문서 관리
- PDF·이미지 문서 추출과 사용자 확인·수정
- Python 규칙 엔진 기반 문서 내부 판정·교차검증
- 공식 법령·공공자료 RAG 기반 근거 검색
- 확인 질문·수정 요청 문구·체크리스트·계약 직후 행동 안내
- 분석 결과 저장·재조회
- AI 아바타(TTS + MuseTalk 립싱크)와 대화하며 질문·답변을 연습하는 계약 연습 시뮬레이션

## 사용자 흐름

<p align="center">
  <img src="docs/assets/readme/user-flow.png" alt="슬기로운 계약생활 사용자 흐름" width="100%">
</p>

AI 추출값과 계약 상황은 분석 전에 사용자가 확인·수정합니다. 분석 결과와 체크리스트는 계약 건 단위로 저장합니다.

상세: [사용자 흐름](docs/planning/user-flow.md)

## 동작 구조

<p align="center">
  <img src="docs/assets/readme/system-architecture.png" alt="슬기로운 계약생활 시스템 구조" width="100%">
</p>

책임 경계:

- **Gemini 3.5 Flash**: 문서 구조화와 설명·질문·행동 생성
- **Python 규칙 엔진**: 판정 상태와 시급도 결정
- **RAG**: 공식 근거 검색. 판정 변경 금지
- **로컬 7B**: 선택적 성능 비교 실험. MVP 크리티컬 패스 제외

상세: [시스템 아키텍처](docs/architecture/system-architecture.md)

## 기술 스택

| 영역 | 기술 |
|---|---|
| Frontend | React · Vite · TypeScript |
| Backend | Python · FastAPI |
| DB / 검색 | PostgreSQL · Chroma · BM25 |
| AI | Gemini 3.5 Flash · gemini-embedding-001 · Cohere rerank-v4.0-pro |
| 문서 처리 | PyMuPDF · Gemini VLM |
| 통합 스키마 | Pydantic (`ai/src/lease_companion_ai/schemas/`) |

## 빠른 실행

필수 환경: Python 3.10, Node.js 20.19+ 또는 22.12+, npm, Docker Desktop.

### 1. 최초 설치

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .\ai -e .\backend
Copy-Item backend\.env.example backend\.env

cd frontend
npm install
cd ..
```

### 2. 전체 MVP 실행

Docker Desktop을 실행한 뒤 저장소 루트에서 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -RealContractValidation
```

- Frontend: `http://127.0.0.1:5173`
- Backend health: `http://127.0.0.1:8301/health`
- API 문서: `http://127.0.0.1:8301/docs`
- 종료: 실행 터미널에서 `Ctrl+C`

Gemini·Cohere 실호출은 선택입니다. `backend/.env`에 `GEMINI_API_KEY`, `COHERE_API_KEY`를 설정합니다. 키가 없으면 지원되는 로컬 fallback을 사용하며, 스캔·사진 OCR에는 `GEMINI_API_KEY`가 필요합니다.

상세 검증 절차: [실전 계약 점검 runbook](docs/testing/real-contract-validation.md)

### DB 없는 최소 데모

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-minimum-mvp.txt
.\scripts\run-minimum-mvp.ps1
```

정식 React Frontend와 PostgreSQL 저장은 포함하지 않습니다.

상세: [최소 MVP runbook](docs/planning/minimum-mvp-runbook.md)

## 팀 구성과 내 역할

| 항목 | 내용 |
|---|---|
| 프로젝트 | ESTCamp 3차 프로젝트 (K-디지털 트레이닝) |
| 팀 규모 | 3인 (coding-jhj · myungkwang · jaehyun7849) |
| 내 역할 | 팀장 · AI·LLM 담당 (역할분담표 기준: 모델 선정·프롬프트·정보 추출·질문 생성·성능 평가) |

- **직접 수행**: 특약사항 근거 기반 검색(RAG)을 구현했습니다. RAGAS 기반 오프라인 평가 파이프라인을 구축했습니다. 정보 추출 검증 플로우를 설계했습니다. 계약 연습 시뮬레이션 엔진(상태 관리·평가 엔진·Gemini 기반 대화 생성, 백엔드 세션 API)을 구현하고, 팀원이 구축한 MuseTalk 아바타 미디어 파이프라인을 이 연습 시스템에 통합했습니다.
- **팀장으로서 조율**: 킥오프 회의에서 "범용 LLM만으로는 기술적 차별성이 부족하다"는 문제를 팀 차원에 제기했습니다. 차별화 축 3가지(문서 교차검증·등기 권리탐지 규칙 엔진·개인정보 비식별 파이프라인)를 정리해 개발 방향을 확정했습니다. 이후 팀원 역할을 재배치했습니다(프론트엔드 전담 폐지 → 백엔드로 흡수, 데이터·RAG 담당으로 재배치).
- **검토/통합**: 모델 관련 작업은 1인 단독 진행을 금지하고 최소 2인 교차검토를 팀 원칙으로 수립했습니다. 팀원 브랜치(`feat/kjh`, `feat/lmk`)를 지속적으로 리뷰·머지했습니다.

## 정량 평가 결과

- RAGAS 기반 평가 파이프라인을 직접 구축해 정량 측정했습니다 — 전체 텍스트가 로컬에 적재된 공식 근거 문서 6종(민법·주택임대차보호법·시행령·표준계약서·확인설명서·체크리스트) 기준 검색 재현율 100%, 정보 추출 정확도 96.7%(Gemini 3.5 Flash, 232/240 필드). 전부 합성 평가셋 기준입니다.

## 기술적 의사결정

**판정을 LLM이 아니라 Python 규칙 엔진에 맡긴 이유**
- 대안: Gemini가 조항을 읽고 바로 "위험/안전"을 판정하게 하는 방식도 가능했습니다.
- 선택: 판정은 규칙 엔진이 전담하고, RAG는 근거 검색만, Gemini는 설명·질문 생성만 담당하도록 했습니다.
- 이유: LLM이 판정까지 직접 내리면 hallucination이 발생했을 때 법적 조언처럼 받아들여질 위험이 있습니다. 그래서 판정 로직은 결정론적으로 고정하고, AI는 설명·근거 제공 역할로 한정했습니다.

## 현재 상태

| 구분 | 상태 |
|---|---|
| 실전 계약 점검 | Backend·Frontend 연결 완료 |
| 계약 연습 | 텍스트 평가·복기, AI 아바타(Supertonic TTS + MuseTalk 립싱크) 영상 생성 연결 완료 |
| 로컬 fallback | FastAPI·PostgreSQL 흐름 검증 기록 있음 |
| 추가 검증 필요 | 실제 Gemini·Cohere 품질·비용, 독립 평가셋 검토 |
| 후속 범위 | 외부 공공데이터(등기·건축물대장 실시간 조회) 자동 연동, 운영 배포 환경의 보안 정책 수립 |

운영 배포 플랫폼은 아직 확정하지 않았습니다.

## 한계와 개선 방향

- 특약사항(조항 단위) RAG 정확도는 66.7%로, 일반 조항 대비 낮습니다. 특약은 표현이 자유로워 패턴화가 어렵습니다.
- 현재 평가 수치는 모두 합성 평가셋 기준이며, 실제 계약서 데이터로의 일반화는 검증되지 않았습니다.

## 프로젝트 구조

| 경로 | 책임 |
|---|---|
| [`frontend/`](frontend/README.md) | 모바일 웹 UI |
| [`backend/`](backend/README.md) | API·오케스트레이션·저장 |
| [`ai/`](ai/README.md) | 문서 처리·구조화·규칙·RAG·생성·평가 |
| [`data/`](data/README.md) | 합성 샘플·규칙·RAG·평가 데이터 |
| [`docs/`](docs/README.md) | 기획·설계·결정 기록·테스트 문서 |

## 데이터 원칙

실제 계약서·개인정보·모델 가중치·체크포인트를 Git에 커밋하지 않습니다. 샘플과 평가 데이터는 가상 또는 완전 비식별 자료만 사용합니다.

상세: [개인정보 보호 원칙](docs/data/privacy-policy.md)

## 주요 문서

- [MVP 범위](docs/planning/mvp-scope.md)
- [판정 명세](docs/data/judgment-spec.md)
- [AI 파이프라인](docs/architecture/ai-pipeline.md)
- [계약 연습 작업 가이드](docs/planning/practice-simulation-work-guide.md)
- [계약 연습 API 검증](docs/testing/practice-real-api-validation.md)
