# evaluation/

## 책임

AI 컴포넌트별·end-to-end 평가를 실행한다. 추출·정규화·로컬 분류·규칙 판정·검색·생성 단계와 전체 흐름의 품질을 측정한다. 평가 데이터는 `data/evaluation/`, 평가 계획은 `docs/ai/evaluation-plan.md`를 따른다.

## 하위 구조

- 컴포넌트별 평가 실행 (extraction / normalization / classification / rules / retrieval / generation)
- end-to-end 파이프라인 평가 실행
- 지표 집계·리포트 (train/validation/test 분리 준수)

## 입력

- `data/evaluation/`의 단계별 평가 데이터, 각 컴포넌트 출력

## 출력

- 컴포넌트별·전체 평가 지표 리포트

## 구현 상태

- `retrieval.py`: retrieval dev/test goldset 로더와 top-k·전체 source recall·로컬 가용 source recall·citation 지표. 기대 source 누락은 원문 부재, R allowlist 제외, BM25 후보 누락, Top-k 밖으로 분해한다. 원문 부재는 중복 제거 source ID 목록으로, 검색 개선 가능한 실패는 사례·규칙·source 단위로 기록한다.
- `offline.py`: 외부 호출 없는 추출·R01~R10·J01~J12·BM25 RAG·template 생성·Guardrail·end-to-end test 기준선.
- `special_clauses.py`: 잠긴 특약 평가셋의 6유형 매칭·Top-3 근거·생성 grounding·종단 흐름·J10 미래 사건 3종을 API 키 없이 측정.
- `scripts/evaluate_ai_pipeline.py`: 전체 로컬 평가를 실행해 `data/evaluation/results/offline_test_metrics.json`에 기록.
- `scripts/evaluate_retrieval.py`: retrieval만 dev/test로 분리해 재측정.
- 상용 provider와 로컬 7B 비교·routing 평가는 승인 및 별도 비교 설정 전까지 미측정.
- **목표 성능 수치는 실제 측정 전 임의로 만들지 않는다.**
- 로컬 7B 파인튜닝 평가(선택 성능비교 실험 — MVP 크리티컬 패스 아님)는 `ai/training/evaluation/`과 역할 구분 유지 (여기는 서비스 파이프라인 평가)

## 특약 오프라인 평가 경계

- 결과: `data/evaluation/results/offline_test_metrics.json`의 `special_clauses`.
- 설정: 결정론적 카탈로그 + BM25 + template fallback. Gemini·Cohere 호출 없음.
- 잠긴 test는 `draft_pending_human_review`다. 측정값은 현재 구현 회귀 기준이며 독립 검토나 운영 성능을 뜻하지 않는다.
