# data/rules/

문서 비교·확인 필요 항목 분류에 쓰는 규칙 데이터 보관 위치.

## 규칙 레코드 필드

각 규칙은 다음을 기록한다. (정의: [`../../docs/data/rule-definition.md`](../../docs/data/rule-definition.md), 판정: [`../../docs/data/judgment-spec.md`](../../docs/data/judgment-spec.md))

- `rule_id` — 규칙 식별자
- `judgment_id` — 연결 판정 (J01–J12)
- `stage` — 적용 계약 단계 (user-flow 3단계 "계약 단계 선택" 입력값. 값 목록 미확정 — TODO)
- `input_fields` — 입력 필드
- `condition` — 조건
- `result` — 결과 상태 (공통 9개: 일치 / 불일치 / 명확 / 불명확 / 미기재 / 상충 가능 / 확인 필요 / 확인 불가 / 적용 제외)
- `urgency` — 시급도 (즉시 확인 / 계약 전 확인 / 계약 직후 조치 / 참고 / 분석 불가)
- `source` — 근거 유형 (공식 자료)
- `version` — 버전

판정별 허용 상태 집합은 판정 명세를 단일 기준으로 한다.

## 현재 상태 / TODO

- 규칙 데이터 없음. TODO: 필드 스키마·핵심 규칙 예시 확정 후 작성.
