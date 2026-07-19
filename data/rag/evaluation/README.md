# Retrieval 평가 결과

- `dev_metrics.json`: `data/sample/expected-results/` 34개 CASE 기반 개발 측정.
- `test_metrics.json`: 분리된 `TEST-001~010` 최종 측정.
- 생성: dev 조정은 `python scripts/evaluate_retrieval.py --split dev`, 최종 test는 `python scripts/evaluate_retrieval.py --split test`로 분리한다.
- 현재 로컬 검색 코퍼스는 재배포 가능한 공식 원문 `SRC-HTA-LAW`, `SRC-HTA-DECREE`, `SRC-STD-LEASE` 3개다. metadata-only 출처는 검색 본문이 없어 정답 포함률이 낮을 수 있으며, 이 제약을 목표치 보정 없이 그대로 기록한다.
- 지표는 합격선이 아니다. 실제 Top-5 정답 포함, source 빈도, 인용 메타데이터 완전성, 비공식 노출, provider fallback 횟수다.

## 2026-07-20 R09 로컬 누락 진단

- 원인: 기본 질의의 `수리·원상복구`와 법령 원문의 `수선` 사이에 토큰 중첩이 없어 `SRC-HTA-LAW`가 BM25 후보 20개에 들지 못했다.
- 수정: 특정 사례 문구를 추가하지 않고 모든 R01~R10에 `rule_evidence_map.csv`의 `relevance_note`를 검색 문맥으로 사용했다. 같은 파일의 source allowlist도 실제 결과에 적용했다.
- dev: 로컬 가용 recall `80/90(88.89%) → 90/90(100%)`, BM25 후보 누락 `10 → 0`.
- test: 로컬 가용 recall `14/15(93.33%) → 15/15(100%)`, 전체 recall `14/39(35.90%) → 15/39(38.46%)`, BM25 후보 누락 `1 → 0`.
- 공통: 비공식 출처 노출 `0` 유지, R/J 상태·시급도와 locked test/goldset 변경 없음.
