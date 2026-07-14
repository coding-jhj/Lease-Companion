# data/rules/

문서 비교·확인 필요 항목 분류에 쓰는 규칙 데이터 보관 위치.

## 파일 (단일 소스)

- **`rule_spec.csv` — 규칙 정의의 단일 소스.** 규칙 판정 로직뿐 아니라 **사용자 리포트 문구(이유·질문·행동·한계)·시급도·근거 ID**를 모두 이 파일 하나에 둔다. 규칙 엔진(`ai/src/lease_companion_ai/rules/`)이 이 파일을 읽는다. **문구를 별도 파일에 중복 정의하지 않는다**(드리프트 방지). LLM은 이 고정 문구를 근거와 함께 다듬기만 하고 `urgency`·판정·핵심 행동을 바꾸지 않는다.
- `source_inventory.csv` — 공식 근거 자료 메타데이터(자료명·발행기관·조문·시행일·URL·수집일·요약 등).
- `rule_evidence_map.csv` — 규칙 ↔ 공식 근거 연결.

## `rule_spec.csv` 컬럼 (14개)

`rule_id` · `rule_name` · `judgment_id`(연결 판정 J01–J12) · `required_inputs` · `required_fields` · `detection_condition` · `exception_condition` · `result_status`(공통 9개) · `urgency`(공통 5개) · `official_source_ids`(`;` 구분) · `report_reason` · `question_template` · `action_template` · `limitations`

- 결과 상태 9개: 일치 / 불일치 / 명확 / 불명확 / 미기재 / 상충 가능 / 확인 필요 / 확인 불가 / 적용 제외
- 시급도 5개: 즉시 확인 / 계약 전 확인 / 계약 직후 조치 / 참고 / 분석 불가
- 판정별 허용 상태 집합은 판정 명세([`../../docs/data/judgment-spec.md`](../../docs/data/judgment-spec.md))를 단일 기준으로 한다.

정의 기준: [`../../docs/data/rule-definition.md`](../../docs/data/rule-definition.md).

## 현재 상태 / TODO

- 1차 규칙 R01~R10 작성 완료(`rule_spec.csv`). 리포트 문구·근거·시급도 포함.
- TODO: 2차 판정(J03·J04·J06·J07·J08·J09·J12) 규칙 추가, source_inventory URL·시행일 확인.
