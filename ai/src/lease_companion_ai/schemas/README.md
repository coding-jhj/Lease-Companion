# schemas/

## 책임

AI 입출력의 정형 구조를 정의한다. 문서별 필드, 판정 결과, 조항 분류, 생성 산출물의 스키마를 한곳에서 관리한다. 모든 AI 결과는 이 스키마로 반환한다. **추출값과 생성값을 구분하는 구조를 포함한다.**

**이 경로의 Pydantic 모델이 런타임 통합 스키마의 단일 원본(canonical runtime schema)이다** (2026-07-16 확정, → [`../../../../docs/decisions/2026-07-16-shared-pydantic-schema.md`](../../../../docs/decisions/2026-07-16-shared-pydantic-schema.md)).

- Backend는 이 공통 타입을 import해 재사용하고 같은 도메인 타입을 중복 정의하지 않는다.
- 필드 규약: 사용자 수정값 `user_corrected_value`, 확인 상태 `verification_status`, confidence 3등급(`추출됨`/`불확실`/`실패`), 원문 증거 `page`/`text`(nullable).
- 배포용 JSON Schema는 손으로 쓰지 않고 Pydantic에서 생성한다. 기존 수동 Schema는 `data/schemas/legacy/`, 현재 canonical v1.1.0 생성본 5개는 `data/schemas/generated/`에 둔다.

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

- **`unified.py` — 통합 스키마 v1.1.0 구현 완료(2026-07-16).** ContractContext·DocumentExtraction·InputSnapshot·CorrectionRequest·AnalysisRunResult + Enum(3등급 confidence·verification_status·결과 역할 2·상태 9·시급도 5). `adapters.py`가 기존 R01~R10 평면 dict와 연결한다(run_rules 무변경).
- JSON Schema 생성: `conda run -n lease-py310 python scripts/generate_unified_schemas.py` → `data/schemas/generated/`. 손으로 수정 금지.
- CASE-001 fixture 생성: `conda run -n lease-py310 python scripts/generate_case001_fixture.py` → `data/sample/fixtures/case-001/`.
- 사용법·인계: [`docs/api/data-contract-v1.md`](../../../../docs/api/data-contract-v1.md)
- `minimum_mvp.py`(기존 dataclass)는 데모 API 호환 wrapper에만 유지한다. 실제 추출·분석 내부 경로는 unified 모델 검증과 어댑터를 통과하며, legacy 평면 요청에서는 수정 이력을 복원하지 않는다.
- `InputSnapshot`은 중첩 필드·목록·매핑까지 불변이며 명시적으로 확인된 필드만 허용한다. `AnalysisRunResult`는 R01~R10을 순서대로 정확히 10개 요구한다.
- `RuleResult.result_type`은 `judgment|fact_flag`로 R01~R10별 고정되며, `triggers_actions`는 현재 status가 후속 질문·체크리스트·행동을 활성화하는지 나타낸다. 모델이 두 값의 조합을 검증한다.
- R01~R10 우선 필드 기준. J01~J12 확장은 필드 추가로 진행(기존 필드 하위 호환).
- TODO: J01~J12 확장 시 필요한 필드를 추가하고 관련 문서·판정 명세를 함께 갱신
