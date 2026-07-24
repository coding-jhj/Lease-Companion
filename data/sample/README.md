# data/sample/

**가상 또는 완전히 비식별화한** 샘플 문서 보관 위치. PoC·MVP·테스트 입력으로 쓴다.

> 실제 개인정보를 포함하지 않는다. 실제 원본은 [`../raw/`](../raw/)(Git 제외)에 둔다.

## 하위 구조

| 폴더 | 내용 |
|------|------|
| `contracts/` | 계약서·특약 샘플 (필수 문서) |
| `registry-records/` | 등기사항증명서 샘플 (교차검증용) |
| `explanation-sheets/` | 중개대상물 확인설명서 샘플 |
| `building-ledgers/` | 건축물대장 샘플 (PoC 참고 범위) |
| `expected-results/` | 위 입력에 대한 기대 추출·판정 결과 (평가 정답셋) |
| `practice-scenarios/` | 계약 연습용 합성 시나리오 원본과 결정적 답변 정답표 |

## 형식

- 문서 이미지·PDF는 비식별 샘플만. 추출 필드는 `document-fields.md` 기준.
- `expected-results/`는 입력 샘플과 매칭되는 기대 출력(추출값·판정 상태·시급도)을 구조화해 둔다. 판정 상태는 공통 9개만 사용.
- `practice-scenarios/`는 실제 계약 `contract_id` 없이 `scenario_id`·버전으로 관리한다. 시나리오 사실·대사와 답변 정답표를 분리하고 사용자 오답을 종합 안전·위험 점수로 바꾸지 않는다.

## 현재 상태 / TODO

- 합성 dev 세트 34쌍 커밋됨: `contracts/`·`registry-records/` 각 34건(파일럿 001~005 + 생성 CASE-006~034, `../gen_dataset.py`로 생성), `expected-results/`에 기존 goldset 3종(`extraction_goldset.jsonl`·`rule_goldset.jsonl`·`rag_goldset.jsonl`)과 J 입력 경계 goldset(`judgment_goldset.jsonl`)이 있다.
- `judgment_goldset.jsonl`은 J01~J13의 허용 상태 51건을 모두 포함하며 `issue_code`로 null 원인을 구분한다. `rules/judgments.py`의 실제 상태·시급도 회귀평가에 사용한다.
- held-out test 10쌍은 `../evaluation/end-to-end/`에 분리(엔티티·표기 스타일 dev와 분리).
- 계약 연습 1단계 fixture `PRACTICE-BROKER-PRESSURE-001`은 합성 전세 상황·4개 목표 행동·답변 상태 6개·고정 입력/출력 예시를 포함한다. `python data/check_dataset.py`가 ID·출처·결정성·개인정보 패턴을 검증한다.
- TODO: 확인설명서·건축물대장 샘플 확충, Phase 4 검수.
