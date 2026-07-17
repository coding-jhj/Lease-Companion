# 2026-07-17 — Alembic 마이그레이션 도구 도입 (제안)

- **상태**: **제안 — 팀 합의 대기** (합의 전 설치·구현하지 않음)
- **범위**: `backend/` DB 스키마 변경 관리 방식. A·C 코드에는 영향 없음.
- **제안자**: 담당 B

## 문제

현재 방식은 기동 시 `Base.metadata.create_all()` + 수동 `ALTER TABLE`이다.

- `create_all`은 **새 테이블만** 만들고 기존 테이블의 컬럼 추가·변경은 적용하지 못한다.
- 모델에 컬럼이 추가될 때마다 팀원 각자 자기 dev DB에 수동 SQL을 실행해야 한다.
  실제 발생 사례 2회: 2026-07-16 `contract_projects` 컬럼 5개, 2026-07-17 `analysis_runs.generation_result`.
- 수동 실행을 빠뜨리면 사람마다 DB 상태가 달라지고, 원인 찾기 어려운 오류가 난다.
- A의 canonical schema v1.2.0 확정(contract_context·GenerationResult) 시 스키마 변경이 또 예정되어 있다.

## 제안

**Alembic 도입** — SQLAlchemy 공식 마이그레이션 도구.

| 항목 | 내용 |
|---|---|
| 설치 | `alembic` 패키지 1개 (`backend/pyproject.toml` 의존성 추가) |
| 초기화 | `backend/alembic/` 생성 + 현재 모델 전체를 기준선(baseline) 마이그레이션으로 저장 |
| 모델 변경 시 | `alembic revision --autogenerate -m "..."` → 마이그레이션 파일을 코드와 함께 커밋 |
| 풀 받은 팀원 | `alembic upgrade head` **한 줄** — 수동 SQL 없음 |
| `create_all` | 마이그레이션으로 일원화 후 제거 (이행기에는 병행 가능) |

## 대안 비교

| 대안 | 평가 |
|---|---|
| 현상 유지 (수동 ALTER) | 도구 없음이 장점. 사람 수·변경 횟수가 늘수록 실수 확률 증가 — 이미 2회 발생 |
| Alembic | SQLAlchemy 제작자가 만든 표준 도구. autogenerate로 작업량 최소. 학습 비용은 명령 2개 수준 |
| 다른 도구(예: raw SQL 스크립트 관리) | Alembic 대비 이점 없음 — 검토 제외 |

## 도입하지 않는 것

- 운영 배포 파이프라인 연동 (운영 배포 플랫폼 자체가 미정 TODO)
- 다운그레이드 마이그레이션 작성 강제 (로컬 MVP에는 과함)

## 주의사항 (도입 시 운영 수칙)

1. **autogenerate는 rename을 인식하지 못한다** — 컬럼·테이블 이름 변경을 "삭제+추가"로 생성하므로 그대로 적용하면 **데이터 유실**. 생성된 마이그레이션 파일은 적용 전 반드시 내용을 확인하고, rename은 `op.alter_column(..., new_column_name=...)`으로 손수 수정한다.
2. **기존 dev DB 이행**: 이미 `create_all`로 만들어진 DB에서 기준선을 실행하면 "테이블 이미 존재" 오류. 기존 DB는 `alembic stamp head`(적용된 것으로 표시만), 새로 만드는 DB만 `alembic upgrade head`.
3. **동시 작업 충돌**: 두 사람이 동시에 revision을 만들면 head가 갈라짐(multiple heads) — merge revision 필요. 현재 DB 모델은 B만 변경하므로 위험 낮음. 모델을 만지는 사람이 늘면 이 수칙 재공유.
4. **테스트와 분리**: 테스트는 sqlite + `create_all` 유지, 마이그레이션은 실DB(PostgreSQL) 전용. 혼용하지 않는다.
5. `server_default` 등 미세 차이는 autogenerate가 놓칠 수 있음 — 1번과 같은 수칙(적용 전 확인)으로 대응.

**GCP 이전 관련**: Cloud SQL PostgreSQL로 이전 시 새 인스턴스에 `alembic upgrade head`로 스키마 재현 — 문제 없음(오히려 이전이 쉬워짐). 데이터 이전은 Alembic 범위 밖(`pg_dump`/`pg_restore` 별도). PostgreSQL 계열 유지가 전제.

## 결정 기준

- 팀 3인 합의 시 도입 확정 → B가 기준선 생성·README 갱신까지 수행 (실작업 1~2시간)
- 합의 전까지는 현행 수동 ALTER 방식 유지 (README의 주의 섹션 참조)
