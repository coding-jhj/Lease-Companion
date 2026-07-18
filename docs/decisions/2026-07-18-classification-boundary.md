# Classification 실행 경계 분리

- 상태: 확정
- 날짜: 2026-07-18
- 대상: AI·Backend 구현자

## 배경

현재 Gemini extraction 응답은 계약 사실과 조항 원문뿐 아니라
deposit_return_condition·repair_responsibility 같은 명확성 후보까지 함께 반환한다.
이 후보는 최종 판정이 아니지만 DocumentExtraction 필드에 들어가 사용자 확인 snapshot과
J10·J11 규칙 입력으로 전달된다. 그 결과 extraction과 classification의 책임이 섞여 있다.

공개 canonical schema는 Backend와 Frontend가 함께 사용하므로 필드를 바로 이동하거나
삭제하면 기존 저장 데이터와 API 계약이 깨진다. 실행 코드를 바꾸기 전에 목표 경계와
입출력 계약을 먼저 고정해야 한다.

## 검토한 선택지

### 선택지 A: Gemini extraction에 통합 유지

한 번의 Gemini 호출에서 사실 추출·조항 원문 추출·조항 유형·명확성 후보를 모두 반환한다.
현재 코드와 schema 변경은 가장 적지만, 추출 사실과 모델 후보의 provenance·평가·재시도를
분리할 수 없다.

### 선택지 B: 별도 classification 계층으로 분리

Extraction은 문서에서 읽은 사실과 조항 원문만 반환한다. Classification은 사용자가 확인한
조항 원문을 입력받아 조항 유형과 명확성 후보를 만든다. Python 규칙 엔진이 두 결과를 함께
사용해 최종 상태·시급도를 정한다.

## 결정

선택지 B를 채택한다.

- Extraction은 문서 사실·조항 원문·원문 위치만 소유한다.
- Classification은 조항 유형·명확성·책임 주체·조건 후보만 소유한다.
- Classification은 별도 실행 단계지만 MVP에서는 Gemini 3.5 Flash provider를 재사용한다.
- Classification은 RuleStatus·urgency·최종 판정 이유를 만들거나 변경하지 않는다.
- J10~J12 최종 판정은 Python 규칙 엔진만 수행한다.
- 로컬 7B는 선택적 비교 실험에서 동일 입출력 계약을 구현할 수 있지만 MVP 경로에는 넣지 않는다.

## Classification 입력 계약

입력은 사용자 확인이 끝난 InputSnapshot에서 만든 읽기 전용 내부 계약이다.

| 필드 | 타입 | 규칙 |
|------|------|------|
| schema_version | 문자열 | canonical schema 버전 |
| input_snapshot_id | 문자열 | 사용자 확인 완료 입력 식별자 |
| contract_id | 정수 | 실제 사용자 계약 건 식별자 |
| case_id | 문자열 또는 null | 합성·평가 사례에서만 사용 |
| clauses | ClauseInput 목록 | J10~J12 대상 조항 |

ClauseInput:

| 필드 | 타입 | 규칙 |
|------|------|------|
| clause_ref | 문자열 | source_field과 ordinal로 만든 실행 내 안정 참조 |
| source_field | enum | deposit_return_clause, repair_responsibility_clause, main_clauses, special_clauses |
| ordinal | 0 이상의 정수 | 목록 내 순서. 단일 문자열은 0 |
| text | 문자열 | 사용자 확인값을 반영한 조항 원문 |
| source_evidence | 객체 | 기존 page·text 원문 증거. 둘 다 null 가능 |

입력에서 제외한다: 이름·주소·연락처·계좌번호 등 classification에 불필요한 개인정보,
기존 RuleStatus·urgency, RAG 근거, 생성 결과.

## Classification 출력 계약

출력은 입력 snapshot에 종속된 후보 집합이며 DocumentExtraction을 덮어쓰지 않는다.

| 필드 | 타입 | 규칙 |
|------|------|------|
| schema_version | 문자열 | 입력과 같은 canonical schema 버전 |
| input_snapshot_id | 문자열 | 입력과 동일 |
| contract_id | 정수 | 입력과 동일 |
| provider_model | 문자열 | 실제 실행 provider/model 식별자 |
| prompt_version | 문자열 | 버전 관리된 classification prompt |
| candidates | ClauseCandidate 목록 | 입력 clause_ref당 1개 |

ClauseCandidate:

| 필드 | 타입 | 규칙 |
|------|------|------|
| clause_ref | 문자열 | 입력 ClauseInput 참조 |
| clause_type | enum | deposit_return, repair_restoration, management_fee, rights_change, other |
| clarity_candidate | enum | 명확, 불명확, 확인 필요 |
| responsible_party_candidate | enum | 임대인, 임차인, 공동, 미지정 |
| condition_candidates | 문자열 목록 | 조항에 명시된 시점·조건만 기록 |
| review_required | boolean | 후보를 규칙 입력 전에 재확인해야 하는지 표시 |

문구 자체가 없으면 ClauseInput을 만들지 않는다. 미기재 여부는 extraction의 null과
source field 존재 상태를 Python 규칙이 판단한다. Classification이 미기재를 추정하지 않는다.

## J 판정 소비 규칙

| 판정 | Extraction 입력 | Classification 후보 | 최종 결정 |
|------|-----------------|--------------------------|-----------|
| J10 | deposit_return_clause | deposit_return 유형·명확성·조건 | Python 규칙 |
| J11 | repair_responsibility_clause | repair_restoration 유형·명확성·책임 주체 | Python 규칙 |
| J12 | main_clauses·special_clauses | 조항별 유형·조건 | Python 규칙의 본문-특약 비교 |

Classification 후보가 없거나 검증에 실패하면 규칙은 추측하지 않고 확인 필요 또는 확인 불가로
처리한다. 후보가 기존 규칙 상태를 덮어쓰는 경로는 허용하지 않는다.

## 전환 계획

이번 결정에서는 공개 schema와 실행 코드를 변경하지 않는다.

1. 다음 canonical schema 버전에 ClassificationInput·ClassificationResult를 추가한다.
2. Backend가 확인 완료 snapshot 뒤 classification 실행·저장 단계를 추가한다.
3. J10~J12 adapter가 raw clause와 classification 후보를 함께 받도록 변경한다.
4. Backend·Frontend·fixture·OpenAPI가 새 계약으로 이동한 뒤
   DocumentExtraction의 deposit_return_condition·repair_responsibility를 제거한다.
5. 이전 필드를 제거하는 schema 버전에서는 하위 호환 여부와 데이터 마이그레이션을 별도 ADR로 결정한다.

## 영향

- ai/extraction: 장기적으로 명확성 후보 생성 책임을 제거한다.
- ai/classification: 별도 실행 코드·prompt·평가 책임을 갖는다.
- ai/rules: J10~J12에서 raw clause와 후보를 함께 검증한다.
- ai/schemas·backend·frontend: 다음 schema 버전 작업에서 공동 변경이 필요하다.
- 현재 v1.8.0 런타임과 API는 그대로 유지한다.
