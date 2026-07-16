# app/models/

## 책임

도메인/영속 모델 계층. 계약 건(`contract_id`) 단위 데이터를 저장하기 위한 엔터티 정의.
DB는 **PostgreSQL**로 확정(2026-07-16, → [`../../../docs/decisions/2026-07-16-mvp-platform-stack.md`](../../../docs/decisions/2026-07-16-mvp-platform-stack.md))되어 **이제 구현 가능**하다. 아직 미구현이며, 구현 시 도메인 필드 정의는 AI Pydantic 공통 타입과 정합을 유지한다.

## 도메인 엔터티 (모델화 대상)

`User` · `ContractProject` · `Document` · `ExtractedField` · `AnalysisRun` · `JudgmentResult` · `EvidenceSource` · `QuestionCard` · `ChecklistItem` · `PostContractAction` · `UserFeedback`

## 관계 (설계 방향, 미확정)

- `User` 1 — N `ContractProject`
- `ContractProject` 1 — N `Document`, `AnalysisRun`, `ChecklistItem`, `PostContractAction`
- `Document` 1 — N `ExtractedField`
- `AnalysisRun` 1 — N `JudgmentResult`; `JudgmentResult` — `EvidenceSource`·`QuestionCard` 연결

## 입출력

- 저장소(`repositories/`)가 이 모델을 통해 영속화
- 스키마(`schemas/`)와 구분 — 스키마는 API 경계용

## TODO

- PostgreSQL 기반 모델·마이그레이션 구현 (후속 구현 작업 — 문서 정비에서는 하지 않음)
- 상세: [`docs/backend/auth-and-persistence.md`](../../../docs/backend/auth-and-persistence.md)
