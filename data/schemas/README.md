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

- **`contract_schema.json` / `registry_schema.json` — legacy/reference (설계 템플릿).** numeric confidence·`user_verified` 등이 2026-07-16 통합 스키마 결정(3등급 confidence·`user_corrected_value`·`verification_status`, → [`../../docs/decisions/2026-07-16-shared-pydantic-schema.md`](../../docs/decisions/2026-07-16-shared-pydantic-schema.md))과 충돌한다. 새 작업의 기준으로 사용하지 않는다. 손으로 재작성하지 않으며, 후속 A 작업에서 `ai/src/lease_companion_ai/schemas/` Pydantic 모델이 생성한 JSON Schema 산출물로 교체한다. 그 전까지 삭제·이동하지 않는다.
- `minimum-mvp-extraction-v1.schema.json` — 최소 MVP 추출값 확인·수정 스키마(field_name enum 12개, verification_status: unverified·confirmed·corrected).
- TODO: 확인설명서·건축물대장 스키마, 판정 리포트 스키마 — Pydantic 생성 방식으로 작성.
