# data/rules/

문서 비교·확인 필요 항목 분류에 쓰는 규칙 데이터 보관 위치.

## 파일 (규칙 축별 단일 소스)

- **`rule_spec.csv` — R01~R24 정의의 단일 소스.** 사용자 리포트 문구·시급도·근거 ID를 포함한다.
- **`judgment_spec.csv` — J01~J12 정의·표현 메타데이터의 단일 소스.** 입력·조건·예외·허용 상태·시급도·근거·버전·구현 위치를 기록하며 `judgments.py`가 사용자 문구와 한계를 직접 읽는다.
- `source_inventory.csv` — 후보 15개의 메타데이터와 `official_verified`·`synthetic_reference`·`unverified`·`excluded` 검증 상태. `official_verified`만 OfficialSource로 노출한다.
- `rule_evidence_map.csv` — 규칙 ↔ 공식 근거 연결.
- `judgment_search_context.csv` — 원문과 판정명의 용어 불일치가 실측된 J 판정만 추가하는 비식별 검색 확장 문맥. 판정·source allowlist는 변경하지 않는다.

## `rule_spec.csv` 컬럼 (14개)

`rule_id` · `rule_name` · `judgment_id`(연결 판정 J01–J12) · `required_inputs` · `required_fields` · `detection_condition` · `exception_condition` · `result_status`(공통 9개) · `urgency`(공통 5개) · `official_source_ids`(`;` 구분) · `report_reason` · `question_template` · `action_template` · `limitations`

- 결과 상태 9개: 일치 / 불일치 / 명확 / 불명확 / 미기재 / 상충 가능 / 확인 필요 / 확인 불가 / 적용 제외
- 시급도 5개: 즉시 확인 / 계약 전 확인 / 계약 직후 조치 / 참고 / 분석 불가
- 판정별 허용 상태 집합은 판정 명세([`../../docs/data/judgment-spec.md`](../../docs/data/judgment-spec.md))를 단일 기준으로 한다.

정의 기준: [`../../docs/data/rule-definition.md`](../../docs/data/rule-definition.md).

## 현재 상태 / TODO

- R01~R24 작성·실행 완료(`rule_spec.csv`). R11~R15·R17~R19는 확인 입력 기반 판정, R16·R23·R24는 질문형, R20~R22는 외부 연동 전 `확인 불가`로 실행한다.
- 2차 판정 J01~J12 작성·실행 완료(`judgment_spec.csv`, `judgments.py`). J goldset 47건 회귀검증 연결.
- J01~J12 공식 근거 검색 연결 완료. 판정별 allowlist 원문이 로컬에 없으면 판정은 유지하고 `evidence_sources=[]`를 반환한다.
- TODO: metadata-only 공식자료 5개의 원문 재배포 가능 여부·적용 범위를 확인하고 R/J 검색을 재평가. (`SRC-MOLIT-CHECKLIST`는 2026-07-20 팀 예외 규정으로 로컬 원문 적재 완료)
