# classification/

## 결정 상태

2026-07-18 ADR에 따라 extraction과 별도 실행 계층으로 분리한다.
canonical v1.9.0은 ClassificationInput·ClassificationResult를 제공하고 v1.8.0 payload 읽기를
허용한다. 현재 확인 완료 InputSnapshot을 ClassificationInput으로 변환하는 순수 builder,
ClassificationProvider·Gemini adapter·결정적 Fake provider, 후보를 추측하지 않는 safe fallback
service가 구현됐다. J10~J12 adapter와 Backend worker도 이 계약으로 연결됐으며,
classification 결과는 내부 저장하고 API에는 노출하지 않는다.

결정과 전환 순서:
[`2026-07-18-classification-boundary.md`](../../../../docs/decisions/2026-07-18-classification-boundary.md)

## 책임

사용자가 확인한 조항 원문을 조항 유형·명확성·책임 주체·조건 후보로 구조화한다.
후보는 Python 규칙 엔진의 참고 입력이며 최종 판정이 아니다.

### 소유하는 값

- clause_type
- clarity_candidate
- responsible_party_candidate
- condition_candidates
- review_required
- provider_model·prompt_version

### 소유하지 않는 값

- 문서에서 읽은 사실·조항 원문·원문 위치: extraction 책임
- 사용자 수정값과 확인 상태: canonical snapshot 책임
- RuleStatus·urgency·판정 이유: rules 책임
- 공식 근거: rag 책임
- 설명·질문·행동: generation 책임

## 입력

확인 완료 InputSnapshot에서 J10~J12 대상 조항만 복사한 ClassificationInput.

- schema_version
- input_snapshot_id
- contract_id
- case_id
- clauses
  - clause_ref
  - source_field
  - ordinal
  - text
  - source_evidence

허용 source_field:

- deposit_return_clause
- repair_responsibility_clause
- main_clauses
- special_clauses

이름·주소·연락처·계좌번호, 기존 판정 상태, RAG·생성 결과는 입력하지 않는다.

`build_classification_input(snapshot)`은 네 허용 필드의 `effective_value`만 읽는다. 단일 조항은
ordinal 0, 배열은 빈 항목을 제외한 기존 순서대로 연속 ordinal을 부여한다. snapshot과
ExtractedField는 변경하지 않는다.

## 출력

입력 snapshot에 종속된 ClassificationResult.

- schema_version
- input_snapshot_id
- contract_id
- provider_model
- prompt_version
- candidates
  - clause_ref
  - clause_type: deposit_return / repair_restoration / management_fee / rights_change / other
  - clarity_candidate: 명확 / 불명확 / 확인 필요
  - responsible_party_candidate: 임대인 / 임차인 / 공동 / 미지정
  - condition_candidates
  - review_required

문구가 없으면 후보를 만들지 않는다. 미기재는 extraction의 null 상태를 Python 규칙이 판단한다.

## J10~J12 연결

| 판정 | 원문 입력 | 후보 | 최종 판정 |
|------|-----------|------|-----------|
| J10 | deposit_return_clause | 반환 유형·명확성·조건 | Python 규칙 |
| J11 | repair_responsibility_clause | 수리 유형·명확성·책임 주체 | Python 규칙 |
| J12 | main_clauses·special_clauses | 조항별 유형·조건 | Python 규칙의 본문-특약 비교 |

## 실행 실패 경계

`ClassificationService.classify(snapshot)`은 입력 생성 → provider 호출 → 입력·결과 교차 검증
순서로 실행한다. 설정 부재·provider 오류·응답 검증 실패·입력 검증 실패 시 원문을 추측하지
않고 `candidates=[]`, `classification_method=safe_fallback`인 결과를 반환한다. 실패 provenance는
`provider_unavailable`·`provider_error`·`response_validation_failed`·`input_validation_failed`
네 내부 코드로만 기록하며 provider·SDK 원문 오류는 결과에 포함하지 않는다.

## 불변조건

- classification은 DocumentExtraction과 InputSnapshot을 수정하지 않는다.
- classification은 RuleStatus·urgency를 생성하거나 변경하지 않는다.
- 입력 clause_ref마다 후보는 최대 1개다.
- 출력은 input_snapshot_id와 prompt_version으로 재현 가능해야 한다.
- provider 실패·응답 검증 실패는 routing에 기록하고, 규칙은 확인 필요 또는 확인 불가로 처리한다.
- 로컬 7B 출력은 선택적 비교 실험에서만 같은 계약을 사용할 수 있다.

## 현재 통합 상태

1. Backend worker가 snapshot 이후 `analyze_with_classification()`을 실행하고 결과를 내부 저장한다.
2. J10~J12 adapter·fixture·평가는 canonical classification 후보 계약을 사용한다.
3. v1.9 신규 extraction은 기존 명확성 후보 필드를 `null`로 반환하고 v1.8 읽기 호환은 유지한다.
