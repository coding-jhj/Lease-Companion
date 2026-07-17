# app/models/

## 책임

PostgreSQL용 SQLAlchemy 영속 모델 계층. 테스트에서는 SQLite JSON variant를 사용한다.

## 현재 모델

- `User`
- `ContractProject`
- `Document`
- `ExtractionRun`
- `CorrectionRecord`
- `InputSnapshotRecord`
- `AnalysisRun`
- `ChecklistItemState`
- `UserFeedback`

판정과 공식 근거는 `AnalysisRun.result`, 생성 안내는 `generation_result`에 분리 저장한다. 원본 추출과 수정 이력, 불변 입력 스냅샷, 재분석 실행도 각각 별도 행으로 보존한다.

## TODO

- Alembic 마이그레이션 체계 도입
- 현재 모델과 PostgreSQL baseline migration 정합성 검증

상세: [`docs/backend/auth-and-persistence.md`](../../../docs/backend/auth-and-persistence.md)
