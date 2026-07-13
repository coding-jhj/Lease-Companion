# app/models/

## 책임

도메인/영속 모델 계층. 계약 건 단위 데이터를 저장하기 위한 엔터티 정의. DB 제품이
확정된 후 구현한다. 그 전에는 **모델·ORM·마이그레이션을 작성하지 않는다.**

## 도메인 엔터티 (DB 확정 후 모델화)

`User` · `ContractProject` · `Document` · `ExtractedField` · `AnalysisRun` · `JudgmentResult` · `EvidenceSource` · `QuestionCard` · `ChecklistItem` · `PostContractAction` · `UserFeedback`

## 관계 (설계 방향, 미확정)

- `User` 1 — N `ContractProject`
- `ContractProject` 1 — N `Document`, `AnalysisRun`, `ChecklistItem`, `PostContractAction`
- `Document` 1 — N `ExtractedField`
- `AnalysisRun` 1 — N `JudgmentResult`; `JudgmentResult` — `EvidenceSource`·`QuestionCard` 연결

## 입출력

- 저장소(`repositories/`)가 이 모델을 통해 영속화
- 스키마(`schemas/`)와 구분 — 스키마는 API 경계용

## TODO (미정)

- DB 제품 확정 → 모델 구현
- 상세: [`docs/backend/auth-and-persistence.md`](../../../docs/backend/auth-and-persistence.md)
