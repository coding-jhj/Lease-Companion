# app/schemas/

## 책임

요청·응답 **Pydantic 모델** 계층. API 입출력 데이터 형태·검증 규칙을 정의한다.
영속 모델(`models/`)과 구분한다 — 스키마는 API 경계용, 모델은 저장용.

**도메인 데이터 타입은 `ai/src/lease_companion_ai/schemas/`의 Pydantic 공통 타입(단일 원본)을 import해 재사용한다. 같은 도메인 타입을 여기에 중복 정의하지 않는다.** 이 계층에는 API 경계 전용 wrapper(요청 파라미터·응답 envelope)만 둔다. (2026-07-16 확정, → [`../../../docs/decisions/2026-07-16-shared-pydantic-schema.md`](../../../docs/decisions/2026-07-16-shared-pydantic-schema.md))

## 입출력

- 입력 스키마: 계약 건 생성, 계약 상황 입력, 문서 업로드 메타, 추출값 확인·수정, 분석 실행 요청, 피드백
- 출력 스키마: 추출값, 판정·근거·질문·행동 리포트, 체크리스트, 계약 직후 행동 상태
- 결과 상태(9개)·시급도(5개)는 루트 [`../../../AGENTS.md`](../../../AGENTS.md)를 단일 기준으로 참조한다.

## TODO (미정)

- 구체 필드·검증 규칙은 API 스키마 확정 시 정의
- 프론트엔드 타입과 동기화 (`docs/api/`)
