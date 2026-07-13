# backend/AGENTS.md

`backend/` 전용 지시서. 루트 [`../AGENTS.md`](../AGENTS.md)를 전제로 하며, 여기서는 백엔드 고유 규칙만 정의한다.

## 규칙

- FastAPI를 사용한다.
- **API 계층 · 의존성 · 서비스 계층 · 저장소 계층**을 분리한다. (`app/api/routes`, `app/api/dependencies`, `app/services`, `app/repositories`)
- 분석은 **계약 건(ContractProject) 단위**로 저장·재조회한다. 단일 세션 중심으로 설계하지 않는다.
- 모든 입력값과 업로드 파일을 검증한다. (형식·크기·개수)
- AI 추출·규칙·RAG 로직을 backend에 **중복 구현하지 않는다.** `ai/` 패키지를 호출한다.
- backend는 로컬 7B·규칙 엔진·RAG·상용 LLM 파이프라인을 **오케스트레이션**하고 결과를 **영속 저장**한다.
- **규칙 엔진 판정을 LLM·로컬 모델이 임의로 변경하지 못하게 한다.** RAG 근거가 없으면 `확인 불가`·`확인 필요`로 반환한다.
- 공통 오류 응답 형식을 사용한다. (`docs/api/error-format.md`)
- 개인정보·문서 내용을 로그에 남기지 않는다.
- 환경변수·비밀정보를 코드에 작성하지 않는다. `.env`에서 읽는다.
- API 스키마 변경 시 `docs/api/`와 프론트엔드 타입을 동기화한다.
- 외부 AI 호출 실패·시간 초과·잘못된 출력을 처리한다.
- 데이터베이스·인증이 미확정이므로 임의로 선택하지 않는다. (저장소·의존성 계층은 인터페이스 경계만 유지)

## 도메인 엔터티

`User` · `ContractProject` · `Document` · `ExtractedField` · `AnalysisRun`(표준 명칭, 동의어 `AnalysisJob`) · `JudgmentResult` · `EvidenceSource` · `QuestionCard` · `ChecklistItem` · `PostContractAction` · `UserFeedback`

## API 책임 영역

`auth` · `users` · `contracts` · `documents` · `extractions` · `analyses` · `results` · `checklists` · `feedback`

경로·메서드·스키마는 미확정. 확정 전 [`docs/api/api-overview.md`](../docs/api/api-overview.md)에 `TODO`로 둔다.

## 계층 경계

| 계층 | 위치 | 책임 |
|------|------|------|
| API 라우트 | `app/api/routes/` | 요청·응답, 입력·업로드 검증, 오류 형식 |
| 의존성 | `app/api/dependencies/` | 요청 의존성 주입(인증 주체·DB 세션·공통 검증) |
| 서비스 | `app/services/` | 계약 건·분석 실행 흐름 오케스트레이션, `ai/` 호출 |
| 저장소 | `app/repositories/` | 도메인 엔터티 영속화 (DB 확정 전 경계만) |
| 스키마 | `app/schemas/` | 요청·응답 Pydantic 모델 |
| 모델 | `app/models/` | 도메인/영속 모델 (DB 확정 후) |
| 워커 | `app/workers/` | 분석 실행 등 비동기·백그라운드 작업 |
| 코어 | `app/core/` | 설정·공통 오류·보안 유틸 |

## 미정 (TODO)

- DB 제품 미확정 → `models/`·`repositories/` 구현 보류, 경계만 유지.
- 인증 방식·라이브러리 미확정 → 임의 도입 금지. 회원 **기능**은 MVP 확정.
- 비동기 분석 상태 전달 방식(폴링 vs 콜백) 미확정.
