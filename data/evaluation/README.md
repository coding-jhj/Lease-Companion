# data/evaluation/

파이프라인 **단계별 평가 데이터** 보관 위치. 평가 계획: [`../../docs/ai/evaluation-plan.md`](../../docs/ai/evaluation-plan.md).

> 목표 성능 수치는 실제 측정 전 임의로 만들지 않는다. 근거 없는 수치 금지.

## 하위 구조 (파이프라인 단계별)

| 폴더 | 평가 대상 |
|------|-----------|
| `extraction/` | 문서 추출(PDF·OCR·VLM·필드 추출) 정확도 |
| `local-model/` | (선택) 로컬 7B 성능비교 실험 조항 분류(라벨 5종) |
| `rules/` | 규칙 엔진 판정(J01–J12) 정확도 |
| `retrieval/` | RAG 검색 품질 (근거 적합성) |
| `generation/` | 상용 LLM 설명·질문·행동 생성 품질 |
| `routing/` | 모델·fallback 라우팅 선택 |
| `end-to-end/` | 입력→리포트 전체 파이프라인 |

## 형식

- 각 단계 평가셋은 입력 + 기대 출력(정답) + 지표로 구성한다.
- 규칙 평가 정답은 공통 9개 상태·시급도로 표기한다.
- 파인튜닝 평가는 `datasets/test`를 사용하며 train/validation과 분리한다.

## 현재 상태

- `end-to-end/` — held-out test 10쌍(TEST-001~010: 계약서·등기부·건축물대장 txt) + 최종 정답셋 3종(`final_testset_extraction.jsonl`·`final_testset_rule.jsonl`·`final_testset_rag.jsonl`). dev(`../sample/`)와 엔티티·표기 스타일 분리.
- `extraction/` — `eval_extraction.py` 추출 평가 스크립트.
- `generation/` — R/J 공통 Guardrail adversarial fixture 3건과 합성 PII tokenization·복원 fixture 5건.
- `retrieval/` — 분리된 dev/test goldset과 `scripts/evaluate_retrieval.py` 평가 실행기. 실측 결과는 `../rag/evaluation/`에 기록한다.
- `results/` — `scripts/evaluate_ai_pipeline.py`로 생성한 외부 호출 없는 test 기준선. 추출·판독 실패 표현·사용자 수정·R01~R10·J01~J12·RAG·R/J template 생성·Guardrail·PII·end-to-end를 분리 기록한다.
- 상용 provider·routing·주관 설명 품질은 비교 설정 또는 사람/독립 judge 라벨이 없어 미측정이다.
