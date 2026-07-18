# Legacy JSON Schema

이 디렉터리는 과거 수동 설계와 최소 MVP 데모 계약을 보존합니다. 런타임·Backend·Frontend의 canonical 계약이 아닙니다.

- `contract_schema.json`, `registry_schema.json`: numeric confidence·`user_verified`를 쓰던 과거 설계 템플릿.
- `minimum-mvp-extraction-v1.schema.json`: canonical Pydantic 도입 전 최소 MVP 추출 확인용 수동 Schema.
- 현재 단일 원본: `ai/src/lease_companion_ai/schemas/unified.py`.
- 배포용 생성본: `../generated/`의 v1.7.0 JSON Schema 8개.

새 코드는 이 파일들을 import·검증 기준으로 사용하지 않습니다. 역사적 비교가 필요할 때만 읽습니다.
