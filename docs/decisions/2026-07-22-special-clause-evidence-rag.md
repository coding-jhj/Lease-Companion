# 특약 공식근거 RAG 오프라인 구현 경계

- 날짜: 2026-07-22
- 상태: 오프라인 구현·자동 검증 완료, 운영 활성화 보류

## 배경

사용자 확인 특약을 6유형으로 나누고, 기존 Python R/J 판정을 유지하면서 특약 원문에 맞는 공식 근거·확인 질문·수정 요청을 제공해야 한다. 카탈로그·RAG·생성이 최종 판정을 바꾸면 기존 계약이 깨진다.

## 결정

1. 카탈로그는 특약 유형 후보와 검색 범위만 제공한다. `RuleStatus`·`urgency`는 Python 규칙 엔진만 결정한다.
2. 검색 질의는 비식별 특약 원문·유형·연결 R/J·상태로 구성한다. 카탈로그가 허용한 `source_id`·`section` 밖 결과는 제거하고 중복 제거 Top-3만 카드에 저장한다.
3. 공식 근거가 없으면 `evidence_sources=[]`를 유지한다. 생성은 법률 결론·확정 수정 문구 없이 확인 질문과 한계만 제공한다.
4. 생성 source ID는 카드 근거의 부분집합이어야 한다. 금지 단정 또는 provider 실패는 결정적 fallback으로 교체하며 Python 판정은 보존한다.
5. Backend는 기존 `AnalysisRun.result.special_clause_reviews`와 `generation_result.special_clause_items`를 사용한다. Frontend는 `확인이 필요한 특약` 카드와 전체 리포트 PDF에 표시한다.
6. J10 미래 사건이 신규 임차인·주택 매각·임대인 자금 사정으로 달라지면 검색 질의·질문·수정 요청은 달라진다. 적용 법적 경계가 같으면 section 결과를 인위적으로 다르게 만들지 않는다.

## 검증 결과

API 키 없는 `offline-regex-bm25-template-v3` 기준:

- 카탈로그 exact match `30/30`, 일반 정상문 오탐 `0/6`
- 검색 Top-3 source `13/15`, section `10/15`, 비공식 노출 `0`
- 생성 schema `7/7`, grounding 위반 `0`, 금지 단정 `0`
- 종단 fixture 5종과 J10 미래 사건 데모 3종 통과
- 외부 provider 호출 `0`

실측 원본은 `data/evaluation/results/offline_test_metrics.json`에 둔다.

## 보류

- 잠긴 test 라벨의 독립 검토
- 실제 Gemini embedding 재인덱싱
- 실제 Cohere rerank와 Gemini 생성 검증
- 운영 활성화

이 단계 전에는 평가셋을 `human_reviewed`, 결과를 운영 검증 완료로 표시하지 않는다.
