# 데이터 계약 v1 인수인계 (A → B·C)

> schema_version **1.8.0 읽기 호환 / 1.9.0 신규 출력** · 작성 2026-07-16 · 최근 갱신 2026-07-19 · 근거 ADR: [`../decisions/2026-07-16-shared-pydantic-schema.md`](../decisions/2026-07-16-shared-pydantic-schema.md), [`../decisions/2026-07-18-classification-boundary.md`](../decisions/2026-07-18-classification-boundary.md)

## 1. 목적과 현재 상태

| 항목 | 위치 |
|---|---|
| Pydantic 단일 원본 | `ai/src/lease_companion_ai/schemas/unified.py` |
| R01–R10 연결 어댑터 | `ai/src/lease_companion_ai/schemas/adapters.py` |
| 생성 JSON Schema 10개 | `data/schemas/generated/` (v1.9 classification input/result 포함, 손으로 수정 금지) |
| CASE-001 fixture 9개 | `data/sample/fixtures/case-001/` |

**현재 상태를 정확히 구분한다:**

- **준비 완료(A)**: 통합 Pydantic 데이터 계약 + 기존 R01–R10 연결 어댑터 + JSON Schema·fixture 생성 + 회귀 테스트 + 실제 minimum MVP AI 파이프라인 내부 연결.
- **주의**: 기존 `/api/minimum-mvp` 데모 API는 요청·응답 호환을 위해 평면 dict를 유지하지만, 내부 추출·분석은 `DocumentExtraction`·`InputSnapshot`·`AnalysisRunResult` 검증을 통과한다. 이 legacy 요청은 최초값과 수정값을 따로 보내지 않으므로 전달된 값을 "사용자가 확인한 최종 effective value"로만 해석하며 수정 이력은 보존하지 않는다.
- **현재 소비 상태**: Backend는 confirm·R01~R10/J01~J12 분석 worker·결과 저장·ContractContext 기반 단계별 안내·prompt version·안정 action item 분리 저장에서 AI canonical 타입을 직접 사용한다. Frontend는 v1.8.0·v1.9.0 wire DTO와 v1.9 fixture, R/J 생성 결과 화면을 지원한다.
- **v1.9.0 구현 상태(A·B)**: `ClassificationInput`·`ClassificationResult`, Gemini provider, provider/safe_fallback provenance, classification→규칙 분석 pipeline helper와 CASE-001 fixture를 구현했다. v1.8.0 payload 읽기는 유지한다. Backend worker는 `analyze_with_classification()`을 호출하고 결과를 내부 저장하며 API에는 노출하지 않는다.
- **v1.4.0 판정 계약**: 기존 R/J 출력 분리를 유지하고, 확인 완료 snapshot에서 판정별 필수 `ExtractedField`를 복사하는 `JudgmentInput`을 추가했다. null J 입력은 구조화 `issue_code`를 요구한다.
- **v1.5.0 ContractContext 활용 계약**: `GenerationResult.stage_guidance`가 immutable `ContractContext`와 J 결과를 결합해 입금 전 질문·서명 전 체크리스트·계약 직후 행동·보관 대상을 결정론적으로 기록한다.
- **v1.6.0 생성 추적 계약**: `GenerationResult.prompt_version`이 사용한 prompt set 버전을 기록한다. 같은 버전은 provider 요청의 `prompt_version`과 `questions/checklists/summaries` 파일 헤더에 일치해야 한다.
- **v1.7.0 J 생성 계약**: `JudgmentGuidance`와 `GenerationResult.judgment_items`를 추가했다. 기존 R `items`와 J `judgment_items`는 별도 ID 축이며, 각 source ID는 해당 분석 항목의 `evidence_sources`만 참조한다.
- **v1.8.0 안정 action item 계약**: R/J `signing_checklist_items`·`post_contract_action_items`에 `{item_key, text}`를 추가했다. `item_key`는 Python이 `result_id|kind|text`에서 생성하며 Backend가 형식·kind 일치를 검증한다.
- **생성 계약 유지**: `GenerationResult`·`RuleGuidance`·`JudgmentGuidance`·`StageGuidance`는 공개 canonical 타입이다. `AnalysisRunResult`와 분리하며 `analysis_run_id`·`contract_id`·`rule_id`·`judgment_id`·공식 `source_ids` 연결을 `validate_generation_result_for_analysis()`로 저장 전에 검증한다.

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

OpenAI 실제 호출은 기본 테스트에서 실행되지 않는다. 키·비용을 별도 승인한 경우에만 합성 CASE-001 하나로 실행한다.

```powershell
$env:RUN_OPENAI_SMOKE='1'
conda run -n lease-py310 python -m pytest ai/tests/generation/test_openai_case001_smoke.py -q
```

검증 결과는 시점마다 달라지므로 이 문서에 고정 개수를 복제하지 않는다. 위 명령과 저장소의 현재 CI·작업 기록으로 확인한다. OpenAI 실제 호출은 기본 회귀에서 제외한다.

## 3. 핵심 모델 요약

전체 JSON 예시는 이 문서에 복사하지 않는다 — fixture 파일이 곧 예시다.

| 모델 | 역할 | 핵심 필드 | fixture |
|---|---|---|---|
| `ContractContext` | 계약 상황 입력 | contract_type·contract_stage·deposit_paid·signed·move_in_date·balance_payment_date·is_proxy_contract | `contract_context.json` |
| `DocumentExtraction` | 문서 1건 추출 결과(수정 전 원본) | document_id·document_type·fields(dict[str, ExtractedField])·warnings | `contract_extraction.json` / `registry_extraction.json` |
| `ExtractedField` | 필드 1개 | field_name·extracted_value·normalized_value·user_corrected_value·verification_status·confidence·source_evidence(page/text)·failure_reason | (위 파일 내부) |
| `CorrectionRequest` | 사용자 수정 요청 | `contract_id` · `corrections[]` (`document_type` · `field_name` · `corrected_value`) | `correction_request.json` |
| `InputSnapshot` | 확인 완료 입력의 **불변** 사본 | input_snapshot_id·contract_id·case_id·**contract_context**·confirmed_fields·confirmed_at | `input_snapshot.json` |
| `JudgmentInput` | J 판정 실행 전용 불변 입력 | input_snapshot_id·contract_id·case_id·judgment_ids·contract_context·contract_fields·registry_fields | (독립 JSON Schema 제공) |
| `ClassificationInput` | 확인 완료 조항 원문 분류 입력 | schema_version·input_snapshot_id·contract_id·clauses | `classification_input.json` |
| `ClassificationResult` | 조항 유형·명확성 후보와 실행 provenance | schema_version·input_snapshot_id·contract_id·provider_model·prompt_version·classification_method·fallback_reason_code·candidates | `classification_result.json` |
| `RuleResult` | 규칙 결과 1개 | **rule_id·rule_name·judgment_id·result_type·triggers_actions·status·urgency·reason·question·recommended_actions·evidence_sources·limitations·completed** | (아래 파일 내부) |
| `JudgmentResult` | J 판정 1개 | judgment_id·judgment_name·status·urgency·triggers_actions·reason·question·recommended_actions·evidence_sources·limitations | (AnalysisRunResult 내부, 독립 JSON Schema 제공) |
| `AnalysisRunResult` | 분석 실행 1회 묶음 | analysis_run_id·input_snapshot_id·contract_id·case_id·results[RuleResult]·judgments[JudgmentResult] | `analysis_run_result.json` |
| `JudgmentGuidance` | J 판정 1개의 생성 안내 | judgment_id·explanation·questions·signing_checklist·post_contract_actions·source_ids·generation_method·provider_model·fallback_reason | (GenerationResult 내부) |
| `StageGuidance` | 계약 상황 기반 단계별 행동 | contract_context·before_deposit_questions·signing_checklist·post_contract_actions·record_retention | (GenerationResult 내부) |
| `GenerationResult` | guardrail 통과 생성 결과 | schema_version·analysis_run_id·prompt_version·items[RuleGuidance]·judgment_items[JudgmentGuidance]·stage_guidance·guardrail_passed | `generation_result.json` |

**Enum 허용값**: `confidence` = `추출됨`·`불확실`·`실패`(숫자 거부) / `verification_status` = `unverified`·`confirmed`·`corrected` / `issue_code` = `not_stated`·`unreadable`·`ambiguous`·`parse_failed`·`not_applicable` / `result_type` = `judgment`·`fact_flag` / `status` 9개·`urgency` 5개 = 루트 `AGENTS.md` 기준 / `document_type` = `contract`·`registry`.

**공통 값 규약**: `contract_id` = Backend DB와 같은 **양의 정수**(fixture `1001`, 문자열·bool 거부) / `case_id` = 합성 평가 문자열(`CASE-001`) / `contract_type` = `전세`·`보증부 월세`·`일반 월세` / `contract_stage` = `계약금 입금 전`·`서명 전`·`계약 직후`.

**공통 규칙**: R01–R10 필수 13키는 값이 null이어도 항상 존재 · 판독 실패 = null + `confidence:"실패"` + `failure_reason` · 빈 목록 금지 · `source_evidence.page`/`text`는 키 상존·값 null 허용 · 필드 타입은 모델이 강제(예: `owner_names`는 비어 있지 않은 `string[]`) · `InputSnapshot`은 `contract_context`를 포함하고 양쪽 `contract_id` 일치를 검증하며 애플리케이션의 일반 변경 API에서 내부 필드·목록·매핑 수정을 차단 · `AnalysisRunResult.results`는 R01–R10을 순서대로 정확히 10개 요구 · `judgments`는 빈 목록 또는 J01~J12 전체 순서만 허용.

**결과 역할·행동 규칙**: `result_type`은 R01·R02·R06·R08·R09=`judgment`, R03·R04·R05·R07·R10=`fact_flag`로 고정된다. `triggers_actions`는 현재 status가 `일치`·`명확`·`적용 제외`면 `false`, 그 외(`불일치`·`불명확`·`미기재`·`상충 가능`·`확인 필요`·`확인 불가`)면 `true`다. 모델은 잘못된 조합을 거부한다.

## 4. 사용자 수정 흐름

```text
CorrectionRequest.corrected_value
  → 어댑터 적용 (adapters.apply_correction_request)
  → ExtractedField.user_corrected_value 에 저장
  → verification_status = corrected
```

원래 `extracted_value`는 **그대로 유지**된다. frozen `ExtractedField`와 `apply_correction()`의 새 객체 생성 방식이 최초값을 보존한다. 규칙 입력 우선순위: `user_corrected_value` → `normalized_value` → `extracted_value` (`ExtractedField.effective_value`).

`build_snapshot()`은 `contract_context`를 필수로 받으며 `unverified` 필드를 자동 승인하지 않는다. 인증된 사용자 확인 동작 이후 `confirm_document()`를 호출해야 하며, 미확인 필드가 남으면 스냅샷 생성·분석을 거부한다.

## 5. B 담당 (Backend·저장)

해야 할 일:

- 공통 AI 패키지 Pydantic 모델을 import한다. Backend에서 같은 도메인 모델을 **중복 정의하지 않는다**.
  ```python
  from lease_companion_ai.schemas.unified import (
      AnalysisRunResult, DocumentExtraction, GenerationResult, InputSnapshot,
      validate_generation_result_for_analysis,
  )
  doc = DocumentExtraction.model_validate_json(raw_json)   # 검증
  raw = doc.model_dump_json()                              # 저장용 직렬화
  ```
- CASE-001 fixture 9개를 API·저장 테스트 입력으로 사용한다.
- 최초 `DocumentExtraction`(수정 전 원본)을 보존하고, `CorrectionRequest`를 수정 이력으로 보존한다.
- `InputSnapshot`을 불변 입력 사본으로, `AnalysisRunResult`를 실행별로 저장한다.
- `RuleResult.result_type`은 문자열, `triggers_actions`는 불리언으로 원형 그대로 저장한다.
- 저장 후 조회한 JSON이 `model_validate_json`을 통과하는지 확인한다.
- 기존 legacy minimum MVP API(`/api/minimum-mvp/*`)와 새 API 경계를 혼용하지 않는다 — 새 저장 경계는 통합 모델만 사용.
- `backend/app/schemas/contract.py`는 canonical `ContractType`·`ContractStage`를 직접 import해 요청·응답과 OpenAPI 값을 공유한다.
- `AnalysisRunResult`를 먼저 저장하고, `GenerationResult`는 `validate_generation_result_for_analysis()` 통과 후 별도 `generation_result`에 저장한다. 생성 실패는 규칙 `result`를 실패로 바꾸지 않는다.

### v1.9 classification worker 연결 계약

A가 제공하는 AI 실행 경계는 아래 순서로 고정한다. Backend는 저장·상태 전이·재시도를 담당하며 AI 내부 후보 생성이나 판정 로직을 다시 구현하지 않는다.

```text
InputSnapshot
  → GeminiClassificationProvider 또는 provider 없음
  → ClassificationService
  → analyze_with_classification
  → ClassificationResult + AnalysisRunResult
```

Backend worker 연결 예시:

```python
import os

from lease_companion_ai.classification.service import ClassificationService
from lease_companion_ai.pipelines.classified_analysis import (
    analyze_with_classification,
)
from lease_companion_ai.providers.gemini_classification import (
    GeminiClassificationProvider,
)

provider = (
    GeminiClassificationProvider()
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    else None
)
classification, analysis = analyze_with_classification(
    snapshot,
    analysis_run_id=run.analysis_run_id,
    classification_service=ClassificationService(provider),
)

run.classification_result = classification.model_dump(mode="json")
run.classification_error = None
run.result = analysis.model_dump(mode="json")
```

저장 규칙:

| 항목 | 규칙 |
|---|---|
| `classification_result` | `ClassificationResult.model_dump(mode="json")` 전체를 provenance 포함 그대로 저장 |
| provider 성공 | `classification_method="provider"`, `fallback_reason_code=null`, 입력 `clause_ref`마다 검증된 후보 1개 |
| safe fallback | `classification_method="safe_fallback"`, 안전한 `fallback_reason_code`, `candidates=[]` |
| `classification_error` | provider 성공과 safe fallback 모두 `null`. fallback 사유를 중복 저장하지 않음 |
| 오류 정보 | provider 원문 예외·응답 원문·PII를 DB·사용자 응답·일반 로그에 저장하거나 노출하지 않음 |
| 분석 지속 | provider 미설정·호출 실패·응답 검증 실패는 `ClassificationService`가 safe fallback으로 흡수하며 R01~R10과 J01~J12 분석을 계속함 |
| 판정 책임 | classification 후보는 J10~J12만 소비. Python 규칙이 `RuleStatus`·`urgency`·최종 이유를 결정하며 classification은 이를 변경하지 않음 |
| R08·R09 | v1.9 deprecated 후보 필드가 `null`이면 `확인 필요` 유지. classification 후보를 구 필드에 다시 주입하지 않음 |

provider 성공 저장 예시:

```json
{
  "schema_version": "1.9.0",
  "input_snapshot_id": "SNAP-1001-001",
  "contract_id": 1001,
  "provider_model": "gemini/gemini-3.5-flash",
  "prompt_version": "classification-v1",
  "classification_method": "provider",
  "fallback_reason_code": null,
  "candidates": [
    {
      "clause_ref": "deposit_return_clause:0",
      "clause_type": "deposit_return",
      "clarity_candidate": "명확",
      "responsible_party_candidate": "임대인",
      "condition_candidates": ["계약 종료일"],
      "review_required": false
    }
  ]
}
```

provider 미설정 safe fallback 저장 예시:

```json
{
  "schema_version": "1.9.0",
  "input_snapshot_id": "SNAP-1001-001",
  "contract_id": 1001,
  "provider_model": "unconfigured",
  "prompt_version": "classification-v1",
  "classification_method": "safe_fallback",
  "fallback_reason_code": "provider_unavailable",
  "candidates": []
}
```

두 결과 모두 정상적인 `ClassificationResult`다. safe fallback은 분석 실행 실패가 아니며, 후보가 없으므로 J10~J12는 원문과 규칙별 입력 경계에 따라 `확인 필요` 또는 `확인 불가`를 반환한다. 내부 classification 결과와 오류는 현재 API에 노출하지 않는다.

Backend 연결 테스트는 최소 다음 경계를 고정한다.

- provider 성공 결과 저장 후 `ClassificationResult.model_validate()` 왕복 성공
- provider 없음·provider 오류·응답 검증 실패에서 safe fallback 저장 후 분석 `completed`
- safe fallback에서도 R01~R10 결과 순서와 기존 판정 불변
- J10~J12만 classification 후보를 소비하고 R08·R09는 `확인 필요` 유지
- 분석 상세 API 응답에 `classification_result`·`classification_error`·provider 원문 오류가 노출되지 않음

**B 인계 확인 체크리스트** (v1.8.0·v1.9.0 공통 R/J 저장과 생성 계약 소비 확인):

- [x] `lease_companion_ai.schemas.unified` import 성공 (GenerationResult·validate_generation_result_for_analysis 포함)
- [x] fixture 9개 `model_validate_json` 검증 성공
- [x] 저장 → 조회 → 재검증 왕복 성공 (sqlite + `AnalysisRun`·`InputSnapshotRecord` 실모델, `model_validate` 재검증 통과)
- [x] 최초 추출값(`extracted_value`)과 수정값(`user_corrected_value`) 분리 저장 확인 (`account_holder`: extracted=null 보존, corrected 별도)
- [x] 필드명 변경 없이 API 응답 가능(별도 매핑표 불필요 — fixture 9개 모두 직렬화 키 = 원본 키)
- [x] `result_type` 문자열·`triggers_actions` 불리언 저장 → 조회 왕복 확인 (R01–R10 전건 원형 일치)
- [x] `ContractContext` 변경에 따라 단계별 질문·체크리스트·계약 직후 행동·보관 대상이 달라지고 저장 → 조회 왕복 확인
- [x] worker에서 `analyze_with_classification()` 실행
- [x] `classification_result` 저장과 내부 provider 오류 미노출 검증

추가 확인(2026-07-17): 스냅샷 `contract_context` 포함·`contract_id` 일치, `validate_generation_result_for_analysis()` fixture 통과. **Backend 연결 완료** — confirm의 ContractContext 결합(`missing_contract_context` 422), 분석 시작 시 계약 상황 변경 차단(`contract_context_changed` 422), 워커 GenerationService·Guardrail 연결(분리 저장).

## 6. C 담당 (Frontend)

해야 할 일:

- `data/sample/fixtures/case-001/`을 mock 데이터로 사용한다. **필드명 임의 변경 금지**.
- confidence 3등급 표시: fixture에 3등급 모두 실재 — `landlord_name`=`추출됨`, registry `issue_date`=`불확실`(값 있음+저신뢰 배지), `account_holder`=수정 전 `실패`(null+`failure_reason` 문구 표시).
- verification_status 변화 처리: 수정 전 전부 `unverified` → 수정 후(`input_snapshot.json`) `account_holder`=`corrected`, 나머지=`confirmed`.
- nullable 원문 증거 처리: `page`/`text`가 null이면 원문 대조 UI를 숨기고 "원문 위치 미확인" 표시(키는 항상 존재).
- 수정 요청은 `correction_request.json` 구조로 생성해 전송한다.
- 결과 화면은 `analysis_run_result.json`의 `status`·`urgency`로 구현한다. **status·urgency를 종합 안전·위험 점수로 바꾸지 않는다**(화면 3그룹 매핑은 `frontend/AGENTS.md`).
- `judgments=[]`이면 R-only 실행으로 처리하고, 값이 있으면 J01~J12 전체를 별도 판정 목록으로 소비한다.
- `result_type`으로 판정(`judgment`)과 사실 플래그(`fact_flag`)를 구분하고, `triggers_actions=true`인 결과만 질문·체크리스트·행동 활성화 대상으로 처리한다.
- B가 OpenAPI에 공개한 `generation_result`를 canonical `GenerationResult` 구조로 소비한다. `null`·생성 실패·`template_fallback`을 처리하고 규칙 `status`·`urgency`·`reason`은 변경하지 않는다.

**Frontend 공식 소비자 검증 체크리스트** (v1.8.0·v1.9.0 DTO와 v1.9 fixture 기준):

- [x] fixture를 별도 변환 없이 로드
- [x] `추출됨`·`불확실`·`실패` 3등급 구분 표시
- [x] `unverified`·`confirmed`·`corrected` 상태 처리
- [x] `correction_request.json` 구조로 수정 요청 JSON 생성
- [x] R01–R10 결과(`RuleResult` 13개 필드) 렌더링
- [x] J01–J12 결과(`JudgmentResult` 10개 필드) 렌더링
- [ ] `result_type`·`triggers_actions` 전용 소비자 동작 검증
- [x] null 원문 증거 처리("원문 위치 미확인")

## 7. 인수인계 완료 조건

| 단계 | 상태 |
|---|---|
| 1. A 패키지 준비 | **완료** — canonical v1.8.0 읽기 호환·v1.9.0 신규 출력, ClassificationInput·ClassificationResult·pipeline helper 포함 Schema 10개, fixture 9개, J gold 47건 |
| 2. B 소비 확인 | **완료** — confirm·R/J 분석·생성 분리 저장, classification worker 실행·내부 저장, provider 성공·실패·safe fallback·API 미노출 검증 완료 |
| 3. Frontend 소비 확인 | **완료** — v1.8.0·v1.9.0 DTO, v1.9 fixture, J10~J12 조항 명확성 화면, classification fallback·내부 오류 미노출, 모바일 E2E 연결 |

최종 소비 완료는 위 체크리스트와 OpenAPI 소비자 테스트에서 **필드명 변경이 없음**을 확인한 시점이다.

**호환성 변경 규칙**: 필드 이름·의미·Enum 변경은 3인 합의 + `SCHEMA_VERSION` 상향 + Schema·fixture 재생성 + 테스트·이 문서 갱신을 함께 한다. 필드는 추가만 한다(J01–J12 확장 포함). 생성 파일은 손으로 수정하지 않는다.

## 8. 알려진 한계

- **정규화 위치**: 현재 legacy 경로는 기존 규칙 엔진 내부 정규화(`normalize_name()`·`normalize_address()`)를 유지한다 — 어댑터는 `normalized_value`를 채우지 않으며 현재 R01–R10 결과에 영향 없다. 스키마 단계 정규화는 후속 책임 분리 작업이다.
- **legacy 수정 이력**: `/api/minimum-mvp/analyze`는 최종 평면 필드만 받으므로 최초 추출값과 수정값을 분리 복원할 수 없다. 새 Backend 저장 경계에서 `DocumentExtraction` 원본과 `CorrectionRequest`를 각각 보존해야 한다.
- **JSON Schema 검증 범위**: Pydantic fixture 검증과 생성 Schema↔모델 드리프트 검증은 완료. 단, 생성 JSON Schema는 Python custom validator 제약(필수 13키 존재, R별 허용 status, 명시적 확인 완료, 빈 목록 금지 등)을 **전부 표현하지 못한다**. 별도 Frontend JSON Schema validator 교차 검증은 C 작업에서 수행 예정이며, C는 실제 API 연결 전에 소비자 측 계약 테스트를 추가해야 한다.
