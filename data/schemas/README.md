# data/schemas/

문서 필드·산출물 **JSON 스키마** 보관 위치. 필드 정의: [`../../docs/data/document-fields.md`](../../docs/data/document-fields.md).

## 책임

- 계약서·등기사항증명서·중개대상물 확인설명서·건축물대장의 추출 필드 스키마.
- 추출·정규화 산출물 스키마(`processed/`와 정합).
- 판정 결과 리포트 스키마(공통 9개 상태·5개 시급도·J01–J12와 정합, [`../../docs/data/judgment-spec.md`](../../docs/data/judgment-spec.md)).

## 형식

- 필드별 데이터 타입·필수/선택·검증 규칙을 명시한다.
- 추출값·정규화값·생성값을 구분한다.

## 현재 상태 / TODO

- **`generated/` — 현재 canonical JSON Schema v1.7.0 생성본(2026-07-18).** `ai/src/lease_companion_ai/schemas/unified.py`의 Pydantic 모델에서 자동 생성한 8개(contract-context·document-extraction·input-snapshot·judgment-input·correction-request·analysis-run-result·judgment-result·generation-result). **손으로 수정하지 않는다.** 재생성 명령:
  `conda run -n lease-py310 python scripts/generate_unified_schemas.py`
  사용법·필드 규약: [`../../docs/api/data-contract-v1.md`](../../docs/api/data-contract-v1.md)
- **`legacy/` — 과거 수동 설계 보존.** `contract_schema.json`·`registry_schema.json`의 numeric confidence·`user_verified`, `minimum-mvp-extraction-v1.schema.json`은 현행 계약과 혼동하지 않는다. 소비 경계는 [`legacy/README.md`](legacy/README.md)를 따른다.
- TODO: 확인설명서·건축물대장 기반 후속 판정 필드 — 필요 시 Pydantic 모델에 필드를 "추가"하고 재생성한다(기존 필드 이름·의미 불변).
