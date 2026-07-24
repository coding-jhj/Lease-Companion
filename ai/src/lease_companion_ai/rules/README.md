# rules/

## 책임

Python 규칙 엔진. 문서 내부 값 판정과 문서 간 교차검증의 **명시적 최종 판정**을 담당한다. LLM·로컬 모델은 이 결과를 임의로 변경하지 않는다. 판정마다 결과 상태(9개)와 시급도(5개)를 부여한다.

## 하위 구조

- `minimum_mvp.py` — R01~R24 규칙. R11~R18의 확인 입력 기반 판정, 시점별 등기 이력 미연결 R19와 외부 연동 대기 R20~R22의 `확인 불가`, R16·R23·R24 질문형 확인을 포함한다.
- `judgments.py` — `JudgmentInput`을 소비하는 J01~J13 전체 판정. J03·J04·J06·J07·J08·J09·J12를 포함한 문서 내부·교차검증과 시급도 부여.

## 입력

- J01~J09: 확인 완료 snapshot의 판정별 계약·등기 필드
- J10~J12: 확인 완료 원문 조항 + 별도 `classification/` 조항 후보
- v1.8·legacy extraction의 구 명확성 후보는 전환 adapter에서만 후보로 변환하며 canonical J 입력 필드에는 포함하지 않는다.

## 출력

- 판정별 결과 상태(`일치`·`불일치`·`명확`·`불명확`·`미기재`·`상충 가능`·`확인 필요`·`확인 불가`·`적용 제외`) + 근거 필드 + 시급도
- **`안전`/`위험`/사기 점수 같은 종합 판정은 내지 않는다.**

## 현재 상태

- J01~J13 결정론적 실행 완료. `data/sample/expected-results/judgment_goldset.jsonl` 51건으로 허용 상태 경계를 회귀검증한다.
- `schemas/adapters.py::analyze_snapshot()`이 신규 실행에서 R01~R24와 J01~J13을 함께 실행한다. 기존 R01~R10 저장 결과는 읽기 호환한다.
- R·J 결과의 공식 근거 검색을 연결했다. 허용된 로컬 원문이 없을 때만 `evidence_sources=[]`을 유지한다.
- Classification 분리는 [`2026-07-18-classification-boundary.md`](../../../../docs/decisions/2026-07-18-classification-boundary.md)에 따라 v1.9 adapter까지 반영했다. 후보가 없거나 검증되지 않으면 J10~J12는 추측하지 않고 안전한 확인 상태를 반환한다.
