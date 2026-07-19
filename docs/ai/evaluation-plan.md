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

## 현재 자동 평가 기준선 (2026-07-19)

`python scripts/evaluate_ai_pipeline.py`는 held-out TEST-001~010과 J goldset 47건을 사용해 외부 호출 없는 기준선을 생성한다. 전체 결과: [`../../data/evaluation/results/offline_test_metrics.json`](../../data/evaluation/results/offline_test_metrics.json).

- 로컬 정규식 추출: 240/240, 100%. canonical schema 검증은 20/20 통과하고, null 판독 실패 표현은 전건 `confidence=실패`·failure reason을 유지한다.
- 사용자 수정: CASE-001 correction의 최초 추출값 보존·수정값 effective 반영·`corrected` 상태 3개 검사를 모두 통과했다.
- R01~R10 상태: 100/100, 100%. 시급도 라벨이 있는 27건도 27/27, 100%.
- J01~J12: 상태·시급도 47/47, 100%. 이 값은 고정 경계 goldset 회귀 결과다.
- BM25 검색: top-5 정답 근거 포함 10/27, 37.04%; 전체 기대 source recall 14/39, 35.90%; 로컬 가용 기대 source recall 14/15, 93.33%; 비공식 source 노출 0건. 누락 25개는 원문 부재 24개와 BM25 Top-20 후보 누락 1개(`TEST-005`·`R09`·`SRC-HTA-LAW`)이며, R allowlist 제외와 Top-5 밖 누락은 0개다.
- J 검색 계약: 행동 발동 gold 32건·기대 source 41개 중 29개를 회수해 recall 70.73%이며, 로컬 원문으로 사용 가능한 기대 source 30개 중 29개를 회수했다. 비공식 source 노출은 0건이다. 남은 격차는 metadata-only·미수집 공식 원문과 로컬 검색 누락으로 분리해 관리한다.
- template 생성: schema 10/10, R trigger coverage 27/27, J trigger coverage 50/50, R/J grounding 위반 0건, 금지 단정 0건, 분석 결과 불변 10/10. 주관적 쉬운 설명 품질은 미측정.
- Guardrail adversarial: 동일 3개 fixture를 R/J 양쪽에 적용해 기대 차단 사유 6/6 일치, false negative 0건.
- PII: 합성 5개 유형의 외부 전송 전 raw PII 제거와 로컬 exact 복원 5/5 통과.
- 로컬 end-to-end: 10/10 완주. 실제 provider latency·비용은 미측정.

추출·R 수치는 고정 합성 TEST-001~010의 정형 문서 기준이며 실제 문서 일반화 성능을 뜻하지 않는다. 검색 개선은 로컬 가용 원문인데 누락된 사례만 BM25·query 구성 대상으로 삼고, 원문 부재는 자료 확보 작업으로 분리한다. 목표치·배포 gate는 합의 전 임의로 설정하지 않는다.

## 미정 (TODO)

- 목표 수치, 자동/수동 평가 비중
- 실제 Gemini 구조화·Hybrid/Rerank·OpenAI 생성의 승인된 provider 기준선
- 사람 또는 독립 judge를 사용한 쉬운 설명·질문·행동 품질 라벨
