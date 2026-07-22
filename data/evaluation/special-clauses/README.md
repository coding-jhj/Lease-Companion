# 특약 평가셋 (DRAFT — 사람 검토 대기)

**review_status: draft_pending_human_review**

이 디렉터리의 평가셋은 AI가 카탈로그와 함께 생성한 **초안(scaffold)**이다. 카탈로그 패턴과
평가셋을 같은 주체가 만들면 "자기 잣대로 자기를 측정"하는 순환이 되므로, **독립적인 사람
검토를 통과하기 전에는 품질 측정(precision/recall 등)의 근거로 사용하지 않는다.**

- 현재 pattern sanity 결과(예: TEST 11/14)는 **품질 지표가 아니라** 패턴 작동·개선점 확인용이다.
- 검토 방법과 합격 기준: [`docs/data/special-clause-review-guide.md`](../../../docs/data/special-clause-review-guide.md)

## 파일
| 파일 | 용도 |
|------|------|
| `catalog_dev.jsonl` | 카탈로그 저작 근거 양성문(개발용) |
| `catalog_test.jsonl` | 블라인드 유형 분류 평가(dev와 문장 미공유, 5범주) |
| `retrieval_dev.jsonl` | 근거 검색 개발 seed |
| `retrieval_test.jsonl` | 문장별 기대 source_id·section |
| `generation_cases.jsonl` | 허용 핵심 의미 + 금지 표현(무효/위법/안전/사기) |

## 5범주 (catalog_test)
`positive_paraphrase`(양성 패러프레이즈) · `normal_negative`(정상 특약) · `negation`(부정문) ·
`conditional_exception`(조건 예외) · `compound`(복합 특약)
