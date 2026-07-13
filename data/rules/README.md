# data/rules/

문서 비교·확인 필요 항목 분류에 쓰는 규칙 데이터 보관 위치.

## 규칙 레코드 필드

각 규칙은 다음을 기록한다. (정의: [`../../docs/data/rule-definition.md`](../../docs/data/rule-definition.md))

- `rule_id` — 규칙 식별자
- `stage` — 적용 단계 (확인 중 / 서명 직전 / 계약 직후)
- `input_fields` — 입력 필드
- `condition` — 조건
- `result` — 결과 상태 (누락 / 모호 / 불일치 / 확인 필요)
- `source` — 근거 (공식 자료)
- `version` — 버전

## 현재 상태 / TODO

- 규칙 데이터 없음. TODO: 필드 스키마·핵심 규칙 예시 확정 후 작성.
