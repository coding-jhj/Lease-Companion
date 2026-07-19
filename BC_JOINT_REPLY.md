# B·C 공동 전달물 (BC_HANDOFF.md 응답)

작성: B·C 확정안 (2026-07-18)

## 전제 (합의·ADR 확정 사항)

- 기준 ADR: `docs/decisions/2026-07-18-classification-boundary.md`
- 다음 canonical schema version은 A가 확정한 **`1.9.0`**이다.
- B-4: classification 상태 **API 미노출** 채택. 기존 analysis
  `pending/running/completed/failed` 폴링 계약을 유지한다.
- schema 전환은 **additive**다. `SchemaVersion`은 전환 기간에 `1.8.0`과
  `1.9.0`을 모두 읽고, 구 필드 제거 버전은 공동 전환 후 별도 ADR로 결정한다.
- 신규 v1.9 extraction의 `deposit_return_condition`과
  `repair_responsibility`는 해석·생성하지 않고 **`null`로 반환**한다.
- classification 결과와 provenance는 Backend 내부 AnalysisRun 저장 범위에 두고
  사용자 API 응답에는 노출하지 않는다.
- 기존 v1.8 snapshot·분석 이력은 변환하거나 덮어쓰지 않고 불변 보존한다.

## 1. 분석 상세 응답 예시 — B 재생성 필요

대상 endpoint:
`GET /api/contracts/{contract_id}/analysis-runs/{analysis_run_id}`

기존 합의 초안의 JSON 예시는 canonical `AnalysisRunResult`의 필수 필드인
`contract_id`, `case_id`, `results`가 빠져 있어 실제 유효 응답 예시가 아니므로
삭제한다.

> **TODO(B):** Backend가 canonical v1.9 타입을 import하고 실제 OpenAPI 연결을
> 완료한 뒤, 생성된 OpenAPI와 실응답을 기준으로 이 절의 JSON 예시를 다시 만든다.
> 손으로 축약한 예시를 계약으로 사용하지 않는다.

재생성 예시에는 최소한 다음을 검증한다.

- 바깥 `AnalysisRunDetail` wire: `analysis_run_id`, `input_snapshot_id`, `status`,
  `error`, `created_at`, `result`, `generation_result`, `generation_status`,
  `generation_error`
- 안쪽 canonical `AnalysisRunResult`: `schema_version`, `analysis_run_id`,
  `input_snapshot_id`, `contract_id`, `case_id`, 순서가 보존된 R01~R10 `results`,
  `judgments`
- classification fallback이 발생해도 별도 공개 상태 필드는 추가하지 않으며,
  규칙이 만든 J10~J12 상태만 기존 결과 구조로 반환
- 과거 v1.8 실행 조회 시 같은 endpoint를 사용하되 저장된 payload의
  `schema_version`과 값은 그대로 유지

## 2. v1.8 → v1.9 필드 전환표

대상: contract `DocumentExtraction` — 추출 API `contract_doc`와 snapshot payload 공통.

| 필드 | v1.8.0 | v1.9.0 | 제거 버전 | Frontend 처리 |
|---|---|---|---|---|
| `deposit_return_condition` | Gemini 해석 후보 값 | optional/deprecated, 신규 출력은 `null` | 별도 ADR | v1.9에서 숨김. 과거 v1.8은 새 원문 필드와 중복되지 않을 때만 읽기 호환 표시 |
| `repair_responsibility` | Gemini 해석 후보 값 | optional/deprecated, 신규 출력은 `null` | 별도 ADR | 상동 |
| `deposit_return_clause` | 조항 원문 | 유지 | 유지 | 사용자 확인·수정 대상 |
| `repair_responsibility_clause` | 조항 원문 | 유지 | 유지 | 사용자 확인·수정 대상 |
| `main_clauses` | 조항 원문 목록 | 유지 | 유지 | 조항별 사용자 확인·수정 대상 |
| `special_clauses_present` | 존재 여부 | 유지 | 유지 | 기존 사실 필드로 유지 |
| `special_clauses` | 특약 원문 목록 | 유지 | 유지 | 조항별 사용자 확인·수정 대상 |
| `ClassificationInput` / `ClassificationResult` | 없음 | 신규 내부 전용 | 유지 | API 미노출 — Frontend 수정 대상 아님 |

## 3. C 화면 전환 계약

### 라벨과 표시 순서

계약서 조항 원문은 다음 순서와 라벨로 표시한다.

1. `deposit_return_clause` — **보증금 반환 조항 원문**
2. `repair_responsibility_clause` — **수리·원상복구 조항 원문**
3. `main_clauses` — **계약서 본문 주요 조항**
4. `special_clauses` — **특약사항**

### 버전별 표시 정책

- v1.9: deprecated 구 후보 필드 2개를 항상 숨긴다.
- v1.8 과거 데이터: 저장값을 바꾸지 않고 읽는다. 대응하는 새 원문 필드에
  표시 가능한 값이 있으면 새 원문만 표시하고 구 후보는 숨겨 중복을 막는다.
  새 원문이 없으면 기존 화면 호환을 위해 구 후보를 표시한다.
- classification 후보는 추출 사실값처럼 표시·수정·저장하지 않는다.

### 배열 편집 방식

- `main_clauses`와 `special_clauses`는 배열 항목 하나당 입력 하나로 편집한다.
- 항목 추가·삭제를 제공하고 순서를 보존한다.
- 쉼표는 조항 본문에 포함될 수 있으므로 쉼표 기반 문자열 분리를 사용하지 않는다.
- 수정 요청의 `corrected_value`도 화면의 항목 배열을 그대로 보낸다.

## 4. 과거 snapshot·분석 이력 정책

- v1.8 snapshot과 분석 이력은 immutable history로 보존하며 v1.9로 backfill하거나
  in-place migration하지 않는다.
- 조회·표시는 payload에 저장된 `schema_version`으로 분기한다.
- 과거 snapshot을 다시 분석해야 하면 기존 snapshot/run을 덮어쓰지 않고, 사용자가
  현재 계약으로 다시 확인한 입력으로 새 v1.9 snapshot과 새 analysis run을 만든다.
- v1.9 기본 출력 활성화는 A canonical schema, B runtime/API, C DTO/UI, fixture와
  OpenAPI의 공동 전환이 끝난 뒤에만 한다. 그전 Backend API는 v1.8 동작을 유지한다.

## 5. Legacy minimum MVP 유지·수정 담당

Legacy minimum MVP는 v1.9 전환 중에도 별도 회귀 경로로 유지한다.

| 범위 | 담당 | 원칙 |
|---|---|---|
| `ai/.../extraction/minimum_mvp.py`, `ai/.../rules/minimum_mvp.py` 등 legacy 추출·규칙 호환 | A | canonical 변경으로 R01~R10 demo가 깨지지 않도록 adapter와 회귀 테스트 유지 |
| `backend/app/mvp_app.py`, legacy endpoint·launcher·Backend smoke | B | v1.8 활성 API가 남아 있는 동안 실행 경로와 fixture 호환 유지 |
| React/Vite 사용자 화면 | C | legacy 정적 UI를 암묵적으로 수정하지 않고, 별도 요청이 있을 때 B와 변경 범위 합의 |

Legacy 경로의 호환 수정이 새 canonical 책임을 다시 legacy extraction에 섞는 근거가
되어서는 안 된다.

## 6. A에게 요청할 v1.9 CASE-001 fixture

현재 `data/sample/fixtures/case-001/`의 fixture는 모두 v1.8.0이므로 A가 canonical
v1.9 모델에서 다음 fixture를 재생성한다.

- v1.9 `contract_extraction.json`
- v1.9 `input_snapshot.json`
- v1.9 `analysis_run_result.json`
- classification safe fallback을 별도 평가할 필요가 있으면
  `ClassificationInput`·`ClassificationResult` 평가 fixture

요구 조건:

- 신규 extraction의 두 deprecated 구 필드는 `null`
- `contract_id`, `case_id`, `input_snapshot_id`, `analysis_run_id` 의미를 혼용하지 않음
- `analysis_run_result.json`은 canonical validation을 통과하고 R01~R10 `results`를
  순서대로 모두 포함
- 기존 v1.8 fixture를 덮어쓸지, 버전별 파일/디렉터리로 병존시킬지는 B·C fixture
  소비 경로를 확인한 뒤 결정

## 7. 작업 순서

A canonical schema·v1.9 fixture → B 저장·worker·API·OpenAPI 연결 →
C DTO·화면·MSW·E2E 전환 → A·B·C 공동 회귀 검증

## 8. A에게 남은 확인 질문

1. **해결(2026-07-19, A 확정 — 안 (가)):** R08·R09를 classification 후보에 연결하는
   adapter는 **만들지 않는다.** ADR 2026-07-18과 §5 경계에 따라 clarity 후보 소비는
   J10·J11만 담당하며, legacy R에 canonical classification 책임을 다시 섞지 않는다.
   - v1.9 extraction이 `deposit_return_condition`·`repair_responsibility`를 `null`로
     반환하면 R08·R09는 단정하지 않고 `확인 필요`로 내려간다. 같은 조항의 실제 clarity는
     사용자에게 노출되는 J10·J11이 후보 경유로 판정하므로 정보 손실이 없다.
   - 전제 정정: `REQUIRED_CONTRACT_FIELDS`에는 두 구 필드가 **이미 포함되지 않으며**,
     canonical 검증기는 `null` 값을 통과시킨다(`type` 검사 전 `None` skip). 따라서
     필수 필드/타입 목록 전환은 필요 없고, 구 필드 제거는 공동 전환 후 별도 ADR로 미룬다.
   - 회귀 잠금: `ai/tests/pipelines/test_minimum_mvp.py::test_v19_null_condition_fields_degrade_r08_r09_to_check_needed`.
   - v1.9 offline(무 classification provider)에서는 J10·J11도 `확인 필요`/`확인 불가`로
     정직하게 내려가며, 실제 clarity는 Gemini classification provider 연결 시 복원된다
     (키·예산 승인 필요, 별도 작업).
2. **해결:** deprecated 기간 신규 v1.9 구 필드 값 정책은 ADR에서 `null` 고정으로 확정됐다.
