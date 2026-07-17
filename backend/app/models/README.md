# app/models/

## 책임

도메인/영속 모델 계층. 계약 건(`contract_id`) 단위 데이터를 저장하기 위한 엔터티 정의.
DB는 **PostgreSQL**로 확정됐다(2026-07-16, → [`../../../docs/decisions/2026-07-16-mvp-platform-stack.md`](../../../docs/decisions/2026-07-16-mvp-platform-stack.md)). `User`와 `ContractProject` 영속 모델은 구현됐고, 후속 모델도 AI Pydantic 공통 타입과 정합을 유지한다.

## 도메인 엔터티

- 구현: `User` · `ContractProject`
- 후속 대상: `Document` · `ExtractedField` · `AnalysisRun` · `JudgmentResult` · `EvidenceSource` · `QuestionCard` · `ChecklistItem` · `PostContractAction` · `UserFeedback`

## 관계 (설계 방향, 미확정)

- `User` 1 — N `ContractProject`
- `ContractProject` 1 — N `Document`, `AnalysisRun`, `ChecklistItem`, `PostContractAction`
- `Document` 1 — N `ExtractedField`
- `AnalysisRun` 1 — N `JudgmentResult`; `JudgmentResult` — `EvidenceSource`·`QuestionCard` 연결

## 입출력

- 저장소(`repositories/`)가 이 모델을 통해 영속화
- 스키마(`schemas/`)와 구분 — 스키마는 API 경계용

## TODO

- 나머지 PostgreSQL 모델과 Alembic 마이그레이션 구현
- 상세: [`docs/backend/auth-and-persistence.md`](../../../docs/backend/auth-and-persistence.md)
