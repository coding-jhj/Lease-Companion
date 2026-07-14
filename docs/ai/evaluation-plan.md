# AI 평가 계획

각 단계를 분리해 평가한다. 서비스 파이프라인 평가는 `ai/src/lease_companion_ai/evaluation/`이 실행하고, 테스트는 `ai/tests/` 하위에서 단계별로 구분한다. 로컬 7B 파인튜닝 평가(베이스 vs 파인튜닝)는 `ai/training/evaluation/`이 담당하며 역할을 구분한다 — 단, 로컬 7B는 MVP 크리티컬 패스에서 제외되어(선정표), 이 평가는 **상용 vs 로컬 성능비교 실험(파인튜닝 B/C안)을 진행할 경우에만** 유효하다. 지표 정의·대상·측정 방법·기록 형식은 [`evaluation-matrix.md`](evaluation-matrix.md)에서 표로 관리한다.

## 평가 구분

| 구분 | 대상 모듈 | 평가 관점 (초안) |
|------|-----------|------------------|
| 인식·추출 | `ingestion` · `extraction` | 문서 인식·핵심 필드 추출 정확도, 구조화 JSON 스키마 준수 |
| 로컬 분류 (선택 실험) | `local_model` · `classification` | 조항 유형·명확성 분류 성능, 베이스 7B vs 파인튜닝 7B, 신뢰도. MVP 크리티컬 패스 아님 — 성능비교 실험 시에만 측정 |
| 규칙 | `rules` | 문서 내부 판정·교차검증 정확도(9개 상태·J01–J12 기준) |
| 검색 | `rag` | 공식 근거 검색 적합성, 정답 근거 포함률, 인용 정확성 |
| 생성 | `generation` | 쉬운 설명·질문·체크리스트·행동 품질, 단정 표현·근거 없는 출력 비율 |
| 라우팅 | `routing` | 로컬 처리율·상용 LLM 재검토율, 상용 단독 vs 하이브리드 비교 |
| 전체 흐름 | `pipelines` | end-to-end 일관성, 문서당 처리 시간, 문서당 상용 API 비용 |

## 원칙

- 평가 데이터는 `data/evaluation/` 하위(extraction/local-model/rules/retrieval/generation/end-to-end)에 두고 train/validation/test를 분리한다.
- 근거 없는 성능 수치·목표치를 문서에 쓰지 않는다. 실제 측정값만 기록한다. 지표는 정의·기록 형식만 먼저 확정한다.
- guardrail 위반(단정 표현·근거 없는 출력)은 생성 평가에서 반드시 확인한다.
- 종합 판정(안전/위험/사기 점수)은 평가 대상이 아니다(사용하지 않음).

## 미정 (TODO)

- 목표 수치, 평가 데이터셋 규모, 자동/수동 평가 비중
