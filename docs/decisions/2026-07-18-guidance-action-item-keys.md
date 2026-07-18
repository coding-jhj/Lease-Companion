# 생성 체크리스트·행동 안정 식별자 결정

- 상태: 확정
- 날짜: 2026-07-18

## 결정

생성 결과의 서명 전 체크리스트와 계약 직후 행동은 기존 문자열 배열을 하위 호환용으로 유지하고, 저장 상태 결합용 항목 배열을 추가한다.

- `signing_checklist_items`: `{ item_key, text }[]`
- `post_contract_action_items`: `{ item_key, text }[]`

`item_key` 형식은 `R01/J01:checklist:<12자리 해시>` 또는 `R01/J01:post_action:<12자리 해시>`다. 해시는 `result_id|kind|text` UTF-8 문자열의 SHA-256 앞 12자리로 생성한다.

## 이유

- LLM이 식별자를 직접 만들지 못하게 한다.
- 출력 순서가 바뀌어도 같은 문구의 완료 상태를 유지한다.
- 문구 의미가 바뀌면 기존 완료 상태가 잘못 승계되지 않는다.
- Backend는 문구를 중복 저장하지 않고 `(contract_id, kind, item_key)`별 완료 상태만 저장한다.

## 호환성

기존 `signing_checklist`와 `post_contract_actions` 문자열 배열은 제거하지 않는다. 이전 생성 결과는 계속 조회할 수 있지만, 저장 상태와 결합되는 새 UI는 안정 식별자 항목을 우선 사용한다.
