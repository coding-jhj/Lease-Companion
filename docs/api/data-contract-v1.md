# 데이터 계약 v1 인수인계 (A → B·C)

> schema_version **1.1.0** · 작성 2026-07-16 · 근거 ADR: [`../decisions/2026-07-16-shared-pydantic-schema.md`](../decisions/2026-07-16-shared-pydantic-schema.md)

## 1. 목적과 현재 상태

| 항목 | 위치 |
|---|---|
| Pydantic 단일 원본 | `ai/src/lease_companion_ai/schemas/unified.py` |
| R01~R10 연결 어댑터 | `ai/src/lease_companion_ai/schemas/adapters.py` |
| 생성 JSON Schema 5개 | `data/schemas/generated/` (손으로 수정 금지) |
| CASE-001 fixture 6개 | `data/sample/fixtures/case-001/` |

**현재 상태를 정확히 구분한다:**

- **준비 완료(A)**: 통합 Pydantic 데이터 계약 + 기존 R01~R10 연결 어댑터 + JSON Schema·fixture 생성 + 회귀 테스트 + 실제 minimum MVP AI 파이프라인 내부 연결.
- **주의**: 기존 `/api/minimum-mvp` 데모 API는 요청·응답 호환을 위해 평면 dict를 유지하지만, 내부 추출·분석은 `DocumentExtraction`·`InputSnapshot`·`AnalysisRunResult` 검증을 통과한다. 이 legacy 요청은 최초값과 수정값을 따로 보내지 않으므로 전달된 값을 "사용자가 확인한 최종 effective value"로만 해석하며 수정 이력은 보존하지 않는다.
- **남은 일**: 새 Backend API·저장 경계에서 이 모델을 사용하는 것은 **B 작업**, fixture 기반 mock→실제 API 연결은 **C 작업**이다. B·C의 실제 소비 확인은 아직 수행되지 않았다(아래 7절 체크리스트).

## 2. 설치·검증 명령

```powershell
python -m pip install -r requirements-minimum-mvp.txt
```

`requirements-minimum-mvp.txt`의 `-e ./ai`, `-e ./backend` 항목 때문에 AI 패키지(`lease_companion_ai`)와 Backend 패키지가 **함께 editable 설치**된다 — B는 별도 설치 없이 `lease_companion_ai.schemas`를 import할 수 있다. 팀 env는 `lease-py310`(Python 3.10) 고정.

```powershell
conda run -n lease-py310 python scripts/generate_unified_schemas.py    # JSON Schema 재생성
conda run -n lease-py310 python scripts/generate_case001_fixture.py    # fixture 재생성(goldset 자체검증 포함)
conda run -n lease-py310 python -m pytest ai/tests backend/tests -q    # 전체 테스트
```

실측 결과(2026-07-16, API 키 차단 로컬 실행): **169 passed, 3 warnings**. Schema·fixture 재생성 후 모델과 일치하며 CASE-001 rule goldset 자체검증 통과. 경고 3건은 Starlette/FastAPI 의존성 deprecation이다.

## 3. 핵심 모델 요약

전체 JSON 예시는 이 문서에 복사하지 않는다 — fixture 파일이 곧 예시다.

| 모델 | 역할 | 핵심 필드 | fixture |
|---|---|---|---|
| `ContractContext` | 계약 상황 입력 | contract_type·contract_stage·deposit_paid·signed·move_in_date·balance_payment_date·is_proxy_contract | `contract_context.json` |
| `DocumentExtraction` | 문서 1건 추출 결과(수정 전 원본) | document_id·document_type·fields(dict[str, ExtractedField])·warnings | `contract_extraction.json` / `registry_extraction.json` |
| `ExtractedField` | 필드 1개 | field_name·extracted_value·normalized_value·user_corrected_value·verification_status·confidence·source_evidence(page/text)·failure_reason | (위 파일 내부) |
| `CorrectionRequest` | 사용자 수정 요청 | contract_id·corrections[](document_type·field_name·corrected_value) | `correction_request.json` |
| `InputSnapshot` | 확인 완료 입력의 **불변** 사본 | input_snapshot_id·contract_id·case_id·confirmed_fields·confirmed_at | `input_snapshot.json` |
| `RuleResult` | 규칙 결과 1개 | **rule_id·rule_name·judgment_id·result_type·triggers_actions·status·urgency·reason·question·recommended_actions·evidence_sources·limitations·completed** | (아래 파일 내부) |
| `AnalysisRunResult` | 분석 실행 1회 묶음 | analysis_run_id·input_snapshot_id·contract_id·case_id·results[RuleResult] | `analysis_run_result.json` |

**Enum 허용값**: `confidence` = `추출됨`·`불확실`·`실패`(숫자 거부) / `verification_status` = `unverified`·`confirmed`·`corrected` / `result_type` = `judgment`·`fact_flag` / `status` 9개·`urgency` 5개 = 루트 `AGENTS.md` 기준(R별 허용 status는 `data/rules/rule_spec.csv`와 일치하도록 모델이 검증) / `document_type` = `contract`·`registry`.

**공통 값 규약**: `contract_id` = Backend DB와 같은 **양의 정수**(fixture `1001`, 문자열·bool 거부) / `case_id` = 합성 평가 문자열(`CASE-001`) / `contract_type` = `전세`·`보증부 월세`·`일반 월세` / `contract_stage` = `계약금 입금 전`·`서명 전`·`계약 직후`.

**공통 규칙**: R01~R10 필수 13키는 값이 null이어도 항상 존재 · 판독 실패 = null + `confidence:"실패"` + `failure_reason` · 빈 목록 금지 · `source_evidence.page`/`text`는 키 상존·값 null 허용 · 필드 타입은 모델이 강제(예: `owner_names`는 비어 있지 않은 `string[]`) · `InputSnapshot`은 애플리케이션의 일반 변경 API에서 내부 필드·목록·매핑 수정을 차단 · `AnalysisRunResult`는 R01~R10을 순서대로 정확히 10개 요구.

**결과 역할·행동 규칙**: `result_type`은 R01·R02·R06·R08·R09=`judgment`, R03·R04·R05·R07·R10=`fact_flag`로 고정된다. `triggers_actions`는 현재 status가 `일치`·`명확`·`적용 제외`면 `false`, 그 외(`불일치`·`불명확`·`미기재`·`상충 가능`·`확인 필요`·`확인 불가`)면 `true`다. 모델은 잘못된 조합을 거부한다.

## 4. 사용자 수정 흐름

```text
CorrectionRequest.corrected_value
  → 어댑터 적용 (adapters.apply_correction_request)
  → ExtractedField.user_corrected_value 에 저장
  → verification_status = corrected
```

원래 `extracted_value`는 **그대로 유지**된다. frozen `ExtractedField`와 `apply_correction()`의 새 객체 생성 방식이 최초값을 보존한다. 규칙 입력 우선순위: `user_corrected_value` → `normalized_value` → `extracted_value` (`ExtractedField.effective_value`).

`build_snapshot()`은 `unverified` 필드를 자동 승인하지 않는다. 인증된 사용자 확인 동작 이후 `confirm_document()`를 호출해야 하며, 미확인 필드가 남으면 스냅샷 생성·분석을 거부한다.

## 5. B 담당 (Backend·저장)

해야 할 일:

- 공통 AI 패키지 Pydantic 모델을 import한다. Backend에서 같은 도메인 모델을 **중복 정의하지 않는다**.
  ```python
  from lease_companion_ai.schemas.unified import DocumentExtraction, InputSnapshot, AnalysisRunResult
  doc = DocumentExtraction.model_validate_json(raw_json)   # 검증
  raw = doc.model_dump_json()                              # 저장용 직렬화
  ```
- CASE-001 fixture 6개를 API·저장 테스트 입력으로 사용한다.
- 최초 `DocumentExtraction`(수정 전 원본)을 보존하고, `CorrectionRequest`를 수정 이력으로 보존한다.
- `InputSnapshot`을 불변 입력 사본으로, `AnalysisRunResult`를 실행별로 저장한다.
- `RuleResult.result_type`은 문자열, `triggers_actions`는 불리언으로 원형 그대로 저장한다.
- 저장 후 조회한 JSON이 `model_validate_json`을 통과하는지 확인한다.
- 기존 legacy minimum MVP API(`/api/minimum-mvp/*`)와 새 API 경계를 혼용하지 않는다 — 새 저장 경계는 통합 모델만 사용.
- `backend/app/schemas/contract.py`는 canonical `ContractType`·`ContractStage`를 직접 import해 요청·응답과 OpenAPI 값을 공유한다.

**B 인계 확인 체크리스트** (B가 직접 확인 — 미리 체크하지 않음):

- [ ] `lease_companion_ai.schemas.unified` import 성공
- [ ] fixture 6개 `model_validate_json` 검증 성공
- [ ] 저장 → 조회 → 재검증 왕복 성공
- [ ] 최초 추출값(`extracted_value`)과 수정값(`user_corrected_value`) 분리 저장 확인
- [ ] 필드명 변경 없이 API 응답 가능(별도 매핑표 불필요)
- [ ] `result_type` 문자열·`triggers_actions` 불리언 저장 → 조회 왕복 확인

## 6. C 담당 (Frontend)

해야 할 일:

- `data/sample/fixtures/case-001/`을 mock 데이터로 사용한다. **필드명 임의 변경 금지**.
- confidence 3등급 표시: fixture에 3등급 모두 실재 — `landlord_name`=`추출됨`, registry `issue_date`=`불확실`(값 있음+저신뢰 배지), `account_holder`=수정 전 `실패`(null+`failure_reason` 문구 표시).
- verification_status 변화 처리: 수정 전 전부 `unverified` → 수정 후(`input_snapshot.json`) `account_holder`=`corrected`, 나머지=`confirmed`.
- nullable 원문 증거 처리: `page`/`text`가 null이면 원문 대조 UI를 숨기고 "원문 위치 미확인" 표시(키는 항상 존재).
- 수정 요청은 `correction_request.json` 구조로 생성해 전송한다.
- 결과 화면은 `analysis_run_result.json`의 `status`·`urgency`로 구현한다. **status·urgency를 종합 안전·위험 점수로 바꾸지 않는다**(화면 3그룹 매핑은 `frontend/AGENTS.md`).
- `result_type`으로 판정(`judgment`)과 사실 플래그(`fact_flag`)를 구분하고, `triggers_actions=true`인 결과만 질문·체크리스트·행동 활성화 대상으로 처리한다.

**C 인계 확인 체크리스트** (C가 직접 확인 — 미리 체크하지 않음):

- [ ] fixture를 별도 변환 없이 로드
- [ ] `추출됨`·`불확실`·`실패` 3등급 구분 표시
- [ ] `unverified`·`confirmed`·`corrected` 상태 처리
- [ ] `correction_request.json` 구조로 수정 요청 JSON 생성
- [ ] R01~R10 결과(`RuleResult` 13개 필드) 렌더링
- [ ] `judgment`·`fact_flag` 구분 및 `triggers_actions` 처리
- [ ] null 원문 증거 처리("원문 위치 미확인")

## 7. 인수인계 완료 조건

| 단계 | 상태 |
|---|---|
| 1. A 패키지 준비 | **완료** (모델·실제 AI 경로 어댑터·Schema·fixture·테스트 169 passed) |
| 2. B 소비 확인 | **대기** — 5절 체크리스트 통과 시 완료 |
| 3. C 소비 확인 | **대기** — 6절 체크리스트 통과 시 완료 |

최종 인수인계는 B·C가 각자 체크리스트를 통과하고 **필드명 변경이 없음**을 확인한 뒤 완료된다.

**호환성 변경 규칙**: 필드 이름·의미·Enum 변경은 3인 합의 + `SCHEMA_VERSION` 상향 + Schema·fixture 재생성 + 테스트·이 문서 갱신을 함께 한다. 필드는 추가만 한다(J01~J12 확장 포함). 생성 파일은 손으로 수정하지 않는다.

## 8. 알려진 한계

- **정규화 위치**: 현재 legacy 경로는 기존 규칙 엔진 내부 정규화(`normalize_name()`·`normalize_address()`)를 유지한다 — 어댑터는 `normalized_value`를 채우지 않으며 현재 R01~R10 결과에 영향 없다. 스키마 단계 정규화는 후속 책임 분리 작업이다.
- **legacy 수정 이력**: `/api/minimum-mvp/analyze`는 최종 평면 필드만 받으므로 최초 추출값과 수정값을 분리 복원할 수 없다. 새 Backend 저장 경계에서 `DocumentExtraction` 원본과 `CorrectionRequest`를 각각 보존해야 한다.
- **JSON Schema 검증 범위**: Pydantic fixture 검증과 생성 Schema↔모델 드리프트 검증은 완료. 단, 생성 JSON Schema는 Python custom validator 제약(필수 13키 존재, R별 허용 status, 명시적 확인 완료, 빈 목록 금지 등)을 **전부 표현하지 못한다**. 별도 Frontend JSON Schema validator 교차 검증은 C 작업에서 수행 예정이며, C는 실제 API 연결 전에 소비자 측 계약 테스트를 추가해야 한다.
