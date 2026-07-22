# Retrieval 평가 결과

- `dev_metrics.json`: `data/sample/expected-results/` 34개 CASE 기반 개발 측정.
- `test_metrics.json`: 분리된 `TEST-001~010` 최종 측정.
- 생성: dev 조정은 `python scripts/evaluate_retrieval.py --split dev`, 최종 test는 `python scripts/evaluate_retrieval.py --split test`로 분리한다.
- 현재 로컬 검색 코퍼스는 로컬 원문 `SRC-HTA-LAW`, `SRC-HTA-DECREE`, `SRC-STD-LEASE`, `SRC-MOLIT-CHECKLIST` 4개다(체크리스트는 2026-07-20 팀 예외 규정 적재). metadata-only 출처는 검색 본문이 없어 정답 포함률이 낮을 수 있으며, 이 제약을 목표치 보정 없이 그대로 기록한다.
- 지표는 합격선이 아니다. 실제 Top-5 정답 포함, source 빈도, 인용 메타데이터 완전성, 비공식 노출, provider fallback 횟수다.

## 2026-07-20 R09 로컬 누락 진단

- 원인: 기본 질의의 `수리·원상복구`와 법령 원문의 `수선` 사이에 토큰 중첩이 없어 `SRC-HTA-LAW`가 BM25 후보 20개에 들지 못했다.
- 수정: 특정 사례 문구를 추가하지 않고 모든 R01~R10에 `rule_evidence_map.csv`의 `relevance_note`를 검색 문맥으로 사용했다. 같은 파일의 source allowlist도 실제 결과에 적용했다.
- dev: 로컬 가용 recall `90/90(100%) → 184/184(100%)`, 전체 recall `94.85%`, 미가용 기대 source `10`, 비공식 노출 0. (2026-07-20 `SRC-MOLIT-CHECKLIST` 적재 반영)
- test: 로컬 가용 recall `15/15(100%) → 38/38(100%)`, 전체 recall `15/39(38.46%) → 38/39(97.44%)`, top-5 정답 포함 `10/27 → 27/27(100%)`, 비공식 노출 0. (2026-07-20 `SRC-MOLIT-CHECKLIST` 적재 반영)
- 공통: 비공식 출처 노출 `0` 유지, R/J 상태·시급도와 locked test/goldset 변경 없음.

## 2026-07-22 특약 Task 10 오프라인 측정

- 설정: 결정론적 6유형 카탈로그 + BM25 + template fallback. 외부 provider 호출 0회.
- 잠긴 특약 retrieval test 7건: 기대 source Top-3 `13/15(86.67%)`, 기대 section Top-3 `10/15(66.67%)`.
- 비공식 출처 노출 `0`, 공식 근거 없음 빈 배열 처리 `1/1`.
- 같은 J10이라도 미래 사건 3종은 검색 질의가 달라진다. 허용 source·section 경계가 같으므로 section 결과를 억지로 다르게 만들지 않는다.
- 결과: `data/evaluation/results/offline_test_metrics.json`의 `special_clauses`.
- 이 값은 `draft_pending_human_review` 회귀 기준이다. 실제 Gemini embedding·Cohere rerank 검증은 보류 상태다.
