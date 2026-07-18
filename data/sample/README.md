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

## 형식

- 문서 이미지·PDF는 비식별 샘플만. 추출 필드는 `document-fields.md` 기준.
- `expected-results/`는 입력 샘플과 매칭되는 기대 출력(추출값·판정 상태·시급도)을 구조화해 둔다. 판정 상태는 공통 9개만 사용.

## 현재 상태 / TODO

- 합성 dev 세트 34쌍 커밋됨: `contracts/`·`registry-records/` 각 34건(파일럿 001~005 + 생성 CASE-006~034, `../gen_dataset.py`로 생성), `expected-results/`에 기존 goldset 3종(`extraction_goldset.jsonl`·`rule_goldset.jsonl`·`rag_goldset.jsonl`)과 J 입력 경계 goldset(`judgment_goldset.jsonl`)이 있다.
- `judgment_goldset.jsonl`은 J01~J12의 허용 상태 47건을 모두 포함하며 `issue_code`로 null 원인을 구분한다. `rules/judgments.py`의 실제 상태·시급도 회귀평가에 사용한다.
- held-out test 10쌍은 `../evaluation/end-to-end/`에 분리(엔티티·표기 스타일 dev와 분리).
- TODO: 확인설명서·건축물대장 샘플 확충, Phase 4 검수.
