# 규칙 엔진 설계

## 역할

Python 규칙 엔진(`rules`)이 정규화된 추출값과 조항 구조화 후보(상용 LLM 구조화 — Gemini 3.5 Flash; 선택적으로 로컬 7B 성능비교 실험 — MVP 크리티컬 패스 제외)를 입력받아 **문서 내부 판정**과 **문서 교차검증**의 **명시적 최종 판정**을 내린다. LLM이 아닌 결정론적 규칙으로 동작한다.

## 입력

- 정규화된 추출 필드 (`normalization` 출력)
- 구조화된 조항 유형·명확성 후보 (`classification` 출력 — 상용 LLM 구조화(Gemini 3.5 Flash) 결과, 선택적으로 로컬 7B 실험 결과를 정리한 값) — 참고 신호이며, 규칙이 최종 판정을 확정한다.

현재 v1.8.0은 공개 schema 호환을 위해 명확성 후보가 Gemini extraction 결과에 포함된다.
canonical v1.9부터 J10~J12는 확인 완료 조항 원문과 별도 classification 결과를 함께 받는다.
경계와 입출력 계약은 [classification ADR](../decisions/2026-07-18-classification-boundary.md)을 따른다.

## 판정 범위

4영역 13항목(J01–J13). 판정 항목과 판정별 적용 가능 상태는 [`../data/judgment-spec.md`](../data/judgment-spec.md)를 기준으로 하며, 여기서 중복 정의하지 않는다.

## 결과 상태 (공통 9개)

`일치` · `불일치` · `명확` · `불명확` · `미기재` · `상충 가능` · `확인 필요` · `확인 불가` · `적용 제외`

- 12개 판정을 동일 상태로 표현하지 않는다. 판정마다 적용 가능한 상태 집합이 다르다(판정 명세 참조).

## 시급도 (5개, 판정 상태와 별도)

`즉시 확인` · `계약 전 확인` · `계약 직후 조치` · `참고` · `분석 불가`

## 원칙

- 규칙 엔진은 상태를 **판정**한다. 계약 안전·위험·전세사기·합법 여부 같은 종합 판정은 내리지 않는다.
- 로컬 모델·상용 LLM은 규칙 엔진 결과를 임의로 변경하지 않는다.
- 각 규칙은 `rule_id·stage·input_fields·condition·result·source·version`을 갖는다. (`../data/rule-definition.md`)
- 등기사항증명서 등 관련 문서와의 값 교차검증(J01·J02·J05 등)은 규칙 엔진이 수행한다.

## 구현 상태

- R01~R10은 `data/rules/rule_spec.csv`와 `rules/minimum_mvp.py`에서 실행한다.
- J01~J13은 `data/rules/judgment_spec.csv`와 `rules/judgments.py`에서 실행하며 goldset 51건으로 검증한다.
- `schemas/adapters.py::analyze_snapshot()`이 R01~R10과 J01~J13을 한 번의 canonical 분석 결과로 구성한다.
- `rag/service.py`가 `data/rules/judgment_spec.csv`의 판정별 공식자료 allowlist를 읽어, 행동이 필요한 J 결과에만 공식 근거를 검색·연결한다. 허용된 로컬 원문이 없으면 `evidence_sources=[]`를 유지한다.
- RAG와 후속 생성은 규칙 엔진이 정한 상태·시급도·판정 이유를 변경하지 않는다.

## 남은 작업

- metadata-only 공식자료의 이용조건을 확인해 허용되는 원문을 추가하고 J 검색 품질을 다시 측정한다.
