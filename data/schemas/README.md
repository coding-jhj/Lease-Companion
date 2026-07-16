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

- **`generated/` — 현재 canonical JSON Schema 생성본(2026-07-16).** `ai/src/lease_companion_ai/schemas/unified.py`의 Pydantic 모델에서 자동 생성한 5개(contract-context·document-extraction·input-snapshot·correction-request·analysis-run-result). **손으로 수정하지 않는다.** 재생성 명령:
  `conda run -n lease-py310 python scripts/generate_unified_schemas.py`
  사용법·필드 규약: [`../../docs/api/data-contract-v1.md`](../../docs/api/data-contract-v1.md)
- **`contract_schema.json` / `registry_schema.json` — legacy/reference (설계 템플릿).** 내부의 numeric confidence·`user_verified`는 과거 설계 표기로, 현행 통합 스키마 결정(3등급 confidence·`user_corrected_value`·`verification_status`, → [`../../docs/decisions/2026-07-16-shared-pydantic-schema.md`](../../docs/decisions/2026-07-16-shared-pydantic-schema.md))과 충돌한다. 새 작업의 기준으로 사용하지 않는다. 손으로 재작성·삭제·이동하지 않는다.
- `minimum-mvp-extraction-v1.schema.json` — 최소 MVP 추출값 확인·수정 스키마(field_name enum 12개, verification_status: unverified·confirmed·corrected). 기존 데모 경로용.
- TODO: 확인설명서·건축물대장 필드, 판정 리포트 스키마 — J01~J12 후속 확장에서 Pydantic 모델에 필드를 "추가"하고 재생성하는 방식으로 작성(기존 필드 이름·의미 불변).
