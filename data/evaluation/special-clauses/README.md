# 특약 오프라인 평가셋 — 잠긴 초안

**review_status: draft_pending_human_review**

API 키 없이 특약 카탈로그·검색·생성 회귀를 개발하기 위한 합성 평가셋이다. 혼자 작업하는
동안 test 정답을 먼저 잠그되, 독립 검토를 받지 않았으므로 `human_reviewed`나 검증된 성능으로
표현하지 않는다.

## dev와 test 경계

- `dev`: 구현 중 반복 확인·수정할 수 있는 개발 자료다.
- `test`: 구현 전에 잠근 회귀 기준이다. 작업 3~10에서 코드 결과에 맞춰 수정하지 않는다.
- test 라벨 오류가 확인되면 이유를 문서에 기록하고 명시적으로 다시 잠근다.
- 정확도·재현율 같은 품질 수치는 독립 검토 전 공식 성능으로 사용하지 않는다.

## 파일

| 파일 | 용도 | 현재 범위 |
|------|------|-----------|
| `catalog_dev.jsonl` | 카탈로그 개발 seed | 유형별 1건 |
| `catalog_test.jsonl` | 잠긴 다중 라벨 분류 정답 | 6유형 × 5범주 = 30건 |
| `retrieval_dev.jsonl` | 근거 검색 개발 seed | 유형별 1건 |
| `retrieval_test.jsonl` | 잠긴 source·section 정답 | 6유형 + 근거 없음 = 7건 |
| `generation_cases.jsonl` | 잠긴 허용 의미·금지 표현 | 6유형 + 근거 없음 = 7건 |
| `locked_test_hashes.json` | 잠긴 test 파일 SHA256 | 3개 파일 |

## catalog_test의 5범주

- `positive_paraphrase`: 탐지돼야 하는 표현 변형
- `normal_negative`: 일반적이고 해당 신호가 없는 문장
- `negation`: 위험 조건을 명시적으로 부정하는 문장
- `conditional_exception`: 임차인 요청·서면 동의 등 제한된 예외 문장
- `compound`: 한 문장에 목표 유형과 다른 유형이 함께 있는 문장

각 행의 `target_catalog_id`는 coverage를 계산하기 위한 기준 유형이다. `expected_catalog_ids`가
실제 정답이며, 복합문은 두 개 이상의 유형을 가질 수 있다. 잠긴 정답이 현재 매칭 코드와
일치하지 않는 사례는 작업 4에서 코드를 보완하며, test 정답을 코드에 맞춰 바꾸지 않는다.

## 잠금 해시

해시는 Git checkout에서도 같도록 `.gitattributes`로 JSONL을 LF에 고정하고 원본 바이트에
SHA256을 적용한다. 실제 값의 단일 원본은 `locked_test_hashes.json`이다.

| 파일 | SHA256 |
|------|--------|
| `catalog_test.jsonl` | `225f3dbf35af011eaa183a449ef9acae518f4ec4aead2285c70b894992c3db6a` |
| `retrieval_test.jsonl` | `30f9a0895d2e5736e5aba5dd55c76755492c4b73dc2d55fd141b88f71f9eb5c5` |
| `generation_cases.jsonl` | `b7d9e772c317d279898c637d49f948fd17972323bdf699421d5066d4d107232e` |

`ai/tests/special_clauses/test_evaluation_fixtures.py`가 coverage, 고유 ID, dev/test 중복,
공식 source·section 범위, 근거 없음 사례, 금지 표현, SHA256을 결정론적으로 검증한다.
