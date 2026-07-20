# 2026-07-20 결정 — SRC-MOLIT-CHECKLIST 로컬 원문 적재 예외

## 결정

`data/rag/sources/README.md`의 재배포 규칙("`usage_terms`에 재배포 허용이 명시된 공식 원문만 로컬 저장")에 **위배되지만**, 안심 전세계약 체크리스트(`SRC-MOLIT-CHECKLIST`) **1건에 한해** 예외로 정규화 원문을 로컬 벡터DB 코퍼스에 적재한다.

- 원본: 국토교통부 보도자료(2025-08-28 발행) 부록 "안심 전세계약 체크리스트" (3·3·3 안심계약 체크리스트).
- 로컬 파일: `data/rag/sources/SRC-MOLIT-CHECKLIST.txt`(정규화 원문), `SRC-MOLIT-CHECKLIST.pdf`(provenance).
- `distribution_mode=local_source`, SHA-256 기록.

## 배경

- 파일 유형 확인 결과 PDF 본문·이미지에서 **공공누리 유형 표시(제1~4유형)가 확인되지 않음**. inventory `document_type`은 "공식 가이드".
- 규칙상 재배포 근거 미충족 → 원래는 `metadata_only` 유지 대상.
- 팀 회의에서 이 자료의 근거 가치(R01·R03~R07·R10·J05 등 다수 판정의 기대 출처)를 고려해 **이 1건만** 예외 적재하기로 결정. 담당A가 담당B에게 작업 위임.

## 범위 제한

- **다른 출처에 이 예외를 확대 적용하지 않는다.** 나머지 metadata_only 5개는 이용조건 확인 전까지 원문 미적재 원칙 유지.
- 공공누리 표시 육안 확인 또는 국토부 개별 표시 조건 문의는 후속 과제로 남긴다. 확인되면 `usage_terms`를 정식 근거로 교체한다.

## 영향 (2026-07-20 실측)

- 로컬 원문 3개 → 4개, `metadata_only` 6개 → 5개.
- test R 전체 recall 15/39(38.46%) → 38/39(97.44%), 로컬 가용 recall 100% 유지, top-5 포함 10/27 → 27/27.
- J 검색 recall 30/41(73.17%) → 33/41(80.49%).
- 비공식 출처 노출 0 유지.
- 관련 갱신: `source_inventory.csv`, `official_sources.jsonl`(재생성), `offline_test_metrics.json`·`dev_metrics.json`·`test_metrics.json`(재생성), 관련 README·평가 문서, `test_source_manifest.py`·`test_offline.py`.
