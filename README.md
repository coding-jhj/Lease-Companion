# 슬기로운 계약생활 (lease-companion)

첫 전월세 계약을 준비하는 **2030 청년 임차인**을 위한 계약 확인 도우미. 회원 기반 모바일 웹앱에서 사용자가 계약 건과 계약 문서를 관리하고, AI·규칙 엔진·RAG가 확인 항목·질문·행동을 근거와 함께 제공한다.

> AI는 계약 가능·안전·전세사기·법률적 결론을 **단정하지 않는다.** 사용자가 직접 확인할 항목·질문·체크리스트·증빙 행동을 제공한다.

## 대상 사용자

- 첫 전월세 계약을 준비하는 2030 청년 임차인
- 대상 계약: 주거용 전세 / 보증부 월세 / 일반 월세

## 해결하려는 문제

첫 계약자는 계약서·특약·등기의 무엇을 확인해야 하는지, 어떤 질문을 해야 하는지, 계약 직후 무슨 권리를 확보해야 하는지 모른다. 정보는 흩어져 있고 판단은 어렵다.

## 최신 MVP

회원 기반 모바일 웹앱에서 사용자가 계약 건과 계약 문서를 관리하고, 상용 LLM(Gemini 3.5 Flash)이 임대차 조항 유형과 불명확성 후보를 구조화한다. Python 규칙 엔진은 계약서와 관련 문서의 값을 교차검증하고, 공식자료 RAG와 상용 LLM(GPT-5.6 Sol)은 판정 근거·쉬운 설명·확인 질문·사용자 행동을 생성한다. 파인튜닝한 로컬 7B는 상용 대비 성능비교 병렬 실험(선택)으로만 유지하며 MVP 크리티컬 패스에서 제외한다.

## 핵심 기능

- 회원가입·로그인·로그아웃·회원 탈퇴
- 사용자별 계약 건 생성·조회·삭제
- 계약 단계·계약 상황 입력
- 계약서·특약 필수 업로드 / 등기사항증명서·중개대상물 확인설명서 선택 업로드
- 디지털 PDF 텍스트 추출(PyMuPDF·PDF.js), 스캔 PDF·사진 OCR(PaddleOCR-VL, 표·체크박스·배치 VLM 통합)
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

- **PoC**: 샘플 계약서·등기 입력 → PDF·OCR 처리(PaddleOCR-VL) → 추출·정규화 → 상용 LLM 구조화(Gemini 3.5 Flash, 로컬 7B는 선택적 성능비교) → 핵심 판정 6개 → 규칙 교차검증 → RAG → 구조화 JSON → 모델 비교평가. 상세: [docs/planning/poc-scope.md](docs/planning/poc-scope.md)
- **MVP**: 회원·계약 건·업로드·확인 수정·12개 판정·등기 교차검증·근거·질문·행동 리포트·저장 재조회·체크리스트·계약 직후 행동 상태 관리. 상세: [docs/planning/mvp-scope.md](docs/planning/mvp-scope.md)

## 전체 시스템 구성

```
frontend (모바일 웹앱)
   ↓
backend (FastAPI: 회원·계약 건·문서·분석·결과 오케스트레이션 + 저장)
   ↓
ai 파이프라인
  문서 입력 → 디지털 PDF 추출(PyMuPDF·PDF.js)·OCR(PaddleOCR-VL, VLM 통합) → 필드 추출 → (사용자 확인·수정)
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
| [`frontend/`](frontend/README.md) | 회원·계약 관리 포함 모바일 웹앱 (프레임워크 미정) |
| [`data/`](data/README.md) | 비식별·합성 샘플, 스키마, 규칙, 라벨, 데이터셋, RAG 자료, 평가, 모델 메타데이터 |
| [`docs/`](docs/README.md) | 기획·아키텍처·API·데이터·AI·백엔드 설계, 결정 기록, 회의록 |

## 기술 방향

**확정 (방향)**

- AI: Python. Backend: Python + FastAPI
- 문서 처리: 디지털 PDF 텍스트 추출(PyMuPDF·PDF.js) + OCR(PaddleOCR-VL, 스캔·사진, VLM 통합)
- 조항 유형·명확성 후보 구조화: 상용 LLM(Gemini 3.5 Flash). 파인튜닝한 로컬 7B(QLoRA)는 상용 대비 선택적 성능비교 실험 — MVP 크리티컬 패스 제외
- 문서 내부 판정·교차검증: Python 규칙 엔진 (최종 판정)
- 근거 검색: 공식 자료 기반 RAG (gemini-embedding-001 + BM25, Cohere rerank-v4.0-pro)
- 설명·질문·행동 생성 및 저신뢰 재검토: 상용 LLM(GPT-5.6 Sol)
- 회원 기반 서비스 + 계약 건 단위 영속 저장

**미정 (TODO — 임의 확정·설치 금지)**

- 프론트엔드 프레임워크 / 데이터베이스 제품 / 벡터 데이터베이스 / 배포 플랫폼
- 인증 세부 기술(회원 기능은 확정, 구현 기술 미정)
- 로컬 7B 베이스 모델 (상용 대비 선택적 성능비교 실험 — 베이스 미정)

## 최소 MVP 실행

현재 최소 MVP는 계약서와 등기사항증명서를 업로드하고, 추출값을 확인·수정한 뒤 R01~R10 결과와 질문·행동·근거 후보를 확인하는 브라우저 데모다.

### 1. 의존성 설치

저장소 루트에서 PowerShell을 열고 실행한다.

```powershell
python -m pip install -r requirements-minimum-mvp.txt
```

### 2. 서버 실행

```powershell
.\scripts\run-minimum-mvp.ps1
```

### 3. 브라우저 접속

```text
http://127.0.0.1:8000
```

개발 확인에는 다음 합성 TXT 샘플을 사용할 수 있다.

- 계약서: `data/sample/contracts/contract_001.txt`
- 등기사항증명서: `data/sample/registry-records/registry_001.txt`

텍스트 레이어가 있는 PDF와 UTF-8 TXT를 지원한다. 스캔·사진 PDF OCR, 회원·DB 저장, 상용 LLM 연동은 아직 포함하지 않는다. 상세한 실행 범위와 제한사항은 [`docs/planning/minimum-mvp-runbook.md`](docs/planning/minimum-mvp-runbook.md)를 참고한다.

전체 MVP의 프론트엔드 스택·DB·인증 방식은 여전히 미정(TODO)이다. 환경변수가 필요한 후속 기능은 `.env.example`을 복사해 `.env`로 사용한다.

## 데이터 / 개인정보 보호 원칙

- 실제 계약서·개인정보·모델 가중치·체크포인트를 Git에 커밋하지 않는다.
- `data/sample`·`data/datasets`에는 가상 또는 완전 비식별화 데이터만 둔다.
- 이름·주소·연락처·계좌번호 등 민감정보 커밋 금지.
- RAG 자료는 공식 법령·표준계약서·공공기관 자료를 우선한다.
- 상세: [docs/data/privacy-policy.md](docs/data/privacy-policy.md)

## 현재 프로젝트 상태

구조·설계 문서·평가 데이터에 더해 **최소 MVP 브라우저 데모**가 구현되어 있다. 디지털 PDF/TXT 추출, 사용자 추출값 확인·수정, R01~R10 규칙 실행, 항목별 질문·행동·근거 후보 표시까지 동작한다.

회원·계약 건 영속 저장·전체 12개 판정·OCR·상용 LLM·정식 프론트엔드는 아직 구현되지 않았다. 최소 MVP 실행 기준은 위 실행 절과 [`docs/planning/minimum-mvp-runbook.md`](docs/planning/minimum-mvp-runbook.md)를 따른다.
