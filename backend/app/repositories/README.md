# app/repositories/

## 책임

도메인 엔터티 영속화 계층. 계약 건(`contract_id`) 단위로 데이터를 저장·재조회한다. 서비스 계층에
저장소 인터페이스만 노출하고, 구체 DB 접근을 캡슐화한다. DB는 **PostgreSQL**로 확정(2026-07-16)되어
구현 가능하다. 현재는 인터페이스 경계만 존재하며 구체 저장소는 미구현이다.

## 저장 대상 도메인 엔터티

`User` · `ContractProject` · `Document` · `ExtractedField` · `AnalysisRun` · `JudgmentResult` · `EvidenceSource` · `QuestionCard` · `ChecklistItem` · `PostContractAction` · `UserFeedback`

## 입출력

- 입력: 서비스 계층의 저장·조회 요청(도메인 객체·식별자)
- 출력: 영속화된 도메인 엔터티, 계약 건 단위 조회 결과
- 저장 상태: 추출값·판정·근거·체크리스트·계약 직후 행동 상태·피드백

## TODO

- PostgreSQL 기반 구체 저장소 구현 (후속 구현 작업)
- `models/`(영속 모델) 구현 후 매핑
- 상세: [`docs/backend/auth-and-persistence.md`](../../../docs/backend/auth-and-persistence.md)
