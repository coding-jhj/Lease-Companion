# Retrieval 평가 결과

- `dev_metrics.json`: `data/sample/expected-results/` 34개 CASE 기반 개발 측정.
- `test_metrics.json`: 분리된 `TEST-001~010` 최종 측정.
- 생성: `python scripts/evaluate_retrieval.py`
- 현재 로컬 검색 코퍼스는 재배포 가능한 공식 원문 `SRC-HTA-LAW`, `SRC-HTA-DECREE` 2개뿐이다. metadata-only 출처는 검색 본문이 없어 정답 포함률이 낮을 수 있으며, 이 제약을 목표치 보정 없이 그대로 기록한다.
- 지표는 합격선이 아니다. 실제 Top-5 정답 포함, source 빈도, 인용 메타데이터 완전성, 비공식 노출, provider fallback 횟수다.
