# schemas/

## 책임

AI 입출력의 정형 구조를 정의한다. 문서별 필드, 판정 결과, 조항 분류, 생성 산출물의 스키마를 한곳에서 관리한다. 모든 AI 결과는 이 스키마로 반환한다. **추출값과 생성값을 구분하는 구조를 포함한다.**

**이 경로의 Pydantic 모델이 런타임 통합 스키마의 단일 원본(canonical runtime schema)이다** (2026-07-16 확정, → [`../../../../docs/decisions/2026-07-16-shared-pydantic-schema.md`](../../../../docs/decisions/2026-07-16-shared-pydantic-schema.md)).

- Backend는 이 공통 타입을 import해 재사용하고 같은 도메인 타입을 중복 정의하지 않는다.
- 필드 규약: 사용자 수정값 `user_corrected_value`, 확인 상태 `verification_status`, confidence 3등급(`추출됨`/`불확실`/`실패`), 원문 증거 `page`/`text`(nullable).
- 배포용 JSON Schema는 손으로 쓰지 않고 Pydantic에서 생성한다. `data/schemas/`의 기존 JSON(`contract_schema.json`·`registry_schema.json`)은 legacy/reference이며 후속 A 작업에서 생성 산출물로 교체한다.

## 하위 구조

- 문서별 필드 스키마 (계약서·등기사항증명서·건축물대장)
- 판정 스키마 (결과 상태 9개, 시급도 5개, 판정 J01~J12)
- 조항 분류 스키마 (`clause_type`·`clarity`·`responsible_party`·`condition`·`review_required`)
- 생성 산출물 스키마 (설명·질문·체크리스트·행동)

## 입력

- 각 모듈이 참조하는 구조 정의 (코드에서 import)

## 출력

- 정형 스키마 객체 (추출·분류·판정·생성 모듈의 반환 형식)

## 현재 상태 / TODO

- 현재 `minimum_mvp.py`(최소 MVP 스키마)만 존재. 통합 Pydantic 모델 코드화는 후속 A 작업.
- R01~R10 우선 필드를 먼저 확정하고, J01~J12 확장은 필드 추가로 진행한다(기존 필드 하위 호환).
- TODO: 문서 필드 정의(`docs/data/document-fields.md`)·판정 명세(`docs/data/judgment-spec.md`)와 정합 확인
