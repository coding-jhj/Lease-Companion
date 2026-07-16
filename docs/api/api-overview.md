# API 개요

> API **책임 영역**만 기록한다. 확정되지 않은 경로·메서드·스키마는 `TODO`로 표시한다.
> 도메인·계층 상세는 [`docs/backend/auth-and-persistence.md`](../backend/auth-and-persistence.md) 참조.

분석은 단일 세션이 아니라 로그인한 사용자의 **계약 건(ContractProject) 단위**로 저장·재조회한다.

## 책임 영역 (9개)

| 영역 | 책임 | 관련 도메인 | 상태 |
|------|------|-------------|------|
| `auth` | 회원가입·로그인·JWT Bearer 토큰 발급 (2026-07-16 인증 방식 확정) | User | TODO: 경로·라이브러리·토큰 정책 미정 |
| `users` | 사용자 프로필·계정 조회·관리 | User | TODO: 경로 미정 |
| `contracts` | 계약 건(`contract_id`) 생성·조회·목록(대시보드), 계약 상황 입력 | ContractProject | TODO: 경로 미정 |
| `documents` | 계약서·등기 등 문서 업로드, 형식·크기·개수 검증. 모의 등기 데이터 연결은 `POST …/registry-link`(2026-07-16 팀 합의 — `case_id` 기준 합성 fixture 연결, 정확한 전체 경로 TODO) | Document | TODO: 경로 미정 |
| `extractions` | AI 추출값 반환, 사용자 확인·수정 반영 | ExtractedField | TODO: 경로 미정 |
| `analyses` | 분석 실행(상용 LLM 구조화(Gemini 3.5 Flash)·규칙 엔진·RAG·상용 LLM 생성(GPT-5.6 Sol); 선택 로컬 7B 실험), 상태 조회 | AnalysisRun | TODO: 경로·상태 전달 방식 미정 |
| `results` | 판정·원문 증거·공식 근거·질문 리포트 조회 | JudgmentResult, EvidenceSource, QuestionCard | TODO: 경로 미정 |
| `checklists` | 서명 전 체크리스트·계약 직후 행동 상태 관리 | ChecklistItem, PostContractAction | TODO: 경로 미정 |
| `feedback` | 사용자 피드백 수집 | UserFeedback | TODO: 경로 미정 |

> 영역 ↔ 도메인은 1:1이 아니다. `auth`·`users`는 모두 `User`를 다루고, `results`는 판정·근거·질문을 함께 조회하며, `checklists`는 체크리스트와 계약 직후 행동을 함께 관리한다.

## 결과 표현 기준

- 결과 상태 9개·시급도 5개·판정 12항목(J01–J12)은 루트 [`AGENTS.md`](../../AGENTS.md)를 단일 기준으로 참조한다. 본 문서에서 재정의하지 않는다.
- `안전`/`위험`/`사기 가능성 점수` 같은 종합 판정 API는 두지 않는다.

## 원칙

- 계층 분리: API 라우트 → 의존성 → 서비스 → 저장소.
- 모든 입력·업로드 파일 검증.
- 규칙 엔진 판정을 LLM이 변경하지 않는다. RAG 근거 없으면 `확인 불가`·`확인 필요`.
- 공통 오류 형식 사용 ([`error-format.md`](error-format.md)).
- 스키마 변경 시 본 문서와 프론트엔드 타입 동기화.

## 확정 / 미정 (TODO)

- 확정(2026-07-16): 인증 방식 **JWT Bearer + bcrypt 계열**(→ [`../decisions/2026-07-16-mvp-platform-stack.md`](../decisions/2026-07-16-mvp-platform-stack.md)). 요청·응답의 도메인 타입은 `ai/src/lease_companion_ai/schemas/` Pydantic 공통 타입을 재사용(→ [`../decisions/2026-07-16-shared-pydantic-schema.md`](../decisions/2026-07-16-shared-pydantic-schema.md)).
- TODO: 구체 경로·메서드·요청/응답 스키마 (확인되지 않은 경로를 임의로 만들지 않는다)
- TODO: JWT 구체 라이브러리·토큰 만료·refresh token·토큰 폐기·서명 키 관리
- TODO: 비동기 분석의 상태 전달 방식(폴링 vs 콜백)
- TODO: `registry-link`의 정확한 전체 경로
