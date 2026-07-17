# app/schemas/

## 책임

API 경계용 Pydantic 요청·응답 wrapper를 정의한다. 영속 모델(`models/`)과 구분한다.

도메인 데이터 타입은 `ai/src/lease_companion_ai/schemas/`의 canonical Pydantic 모델을 import해 재사용한다. 같은 필드를 Backend에서 중복 정의하지 않는다.

현재 auth·contract·document·extraction·analysis·checklist·feedback wrapper가 구현돼 있다. 정확한 공개 계약은 [`docs/api/openapi.json`](../../../docs/api/openapi.json), canonical 계약은 [`docs/api/data-contract-v1.md`](../../../docs/api/data-contract-v1.md)를 기준으로 한다.

변경 시 OpenAPI, canonical schema, Frontend DTO를 함께 확인한다.
