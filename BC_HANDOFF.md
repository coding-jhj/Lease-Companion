# Classification 분리를 위한 B·C 작업 인계서

## 문서 목적

이 문서는 A가 `classification` 실행 계층 구현을 시작하기 전에 B와 C가 결정해야 할 계약과, A 구현 이후 B·C가 연결해야 할 코드를 구분합니다.

- 대상: B(Backend), C(Frontend), A(AI)
- 현재 기준: canonical schema v1.8.0
- 기준 ADR: `docs/decisions/2026-07-18-classification-boundary.md`
- 제외: 실제 provider 유료 smoke, 로컬 7B 선택, 공식자료 원문 확보

## 왜 B·C 결정이 먼저 필요한가

현재 v1.8.0에서는 다음 두 값이 extraction 결과에 들어갑니다.

- `deposit_return_condition`
- `repair_responsibility`

하지만 두 값은 문서에서 읽은 사실이라기보다 Gemini가 해석한 명확성·책임 후보입니다. 목표 구조에서는 다음처럼 분리합니다.

1. Extraction: 계약 사실과 조항 원문만 추출
2. 사용자: 추출된 조항 원문 확인·수정
3. Classification: 확인된 조항 원문에서 유형·명확성·책임 후보 생성
4. Python 규칙: 원문과 후보를 함께 사용해 J10~J12 최종 판정

현재 Frontend는 두 구 필드를 추출 검토 화면에 표시하고, Backend는 확인된 전체 `InputSnapshot`을 JSON으로 저장합니다. A가 필드를 먼저 이동하면 기존 저장 데이터·API DTO·화면이 동시에 깨질 수 있습니다.

## 전체 작업 순서

| 단계 | 담당 | 결과 |
|---|---|---|
| 0 | B·C | 호환·저장·화면 전환 계약 확정. 이 단계가 끝나면 A 시작 가능 |
| 1 | A | 새 canonical 타입·classification 실행·J10~J12 adapter 구현 |
| 2 | B | 새 타입을 import해 저장·worker·API 연결 |
| 3 | C | DTO·추출 검토·상태 화면·MSW·E2E 전환 |
| 4 | A·B·C | OpenAPI·fixture·전체 흐름 공동 회귀 검증 |

B·C는 단계 0에서 코드를 완성할 필요가 없습니다. 아래 결정표와 응답 예시를 확정해 A에게 전달하면 됩니다.

---

## B 작업: A 시작 전에 결정할 사항

### B-1. 기존 데이터 호환 방식 결정

다음 중 하나를 선택해 문서로 남깁니다.

- 권장: 한 schema 버전 동안 구 필드를 유지하고 새 classification 결과를 추가하는 additive 전환
- 대안: 새 버전에서 구 필드를 즉시 제거하고 기존 v1.8 저장 데이터 migration 수행

B가 답해야 하는 질문:

1. 기존 `input_snapshots.payload`의 v1.8 JSON을 계속 조회할 수 있어야 합니까?
2. 기존 분석 이력을 새 schema로 변환합니까, 버전별 그대로 보존합니까?
3. 구 필드 제거 시 migration을 언제, 어떤 명령으로 적용합니까?
4. migration 실패 시 기존 데이터로 되돌리는 기준은 무엇입니까?

권장 결과: 기존 snapshot과 분석 이력은 불변으로 보존하고, 새 실행부터 새 schema를 사용합니다. 구 필드는 공동 전환 완료 전까지 읽기 호환만 유지합니다.

### B-2. Classification 저장 단위 결정

A에게 아래 저장 계약을 전달해야 합니다.

| 항목 | 결정해야 할 내용 |
|---|---|
| 연결 키 | `input_snapshot_id`와 `analysis_run_id` 중 무엇을 기준으로 연결할지 |
| 실행 ID | 별도 `classification_run_id`가 필요한지 |
| 상태 | `pending`·`running`·`completed`·`failed` 사용 여부 |
| 결과 | `ClassificationResult` JSON 저장 위치 |
| provenance | `provider_model`, `prompt_version`, routing/fallback 기록 위치 |
| 오류 | 사용자용 오류와 내부 provider 실패 사유 분리 방식 |
| 재시도 | 같은 snapshot 재시도 시 새 행 생성 또는 기존 행 갱신 여부 |
| stale 복구 | 서버 재시작 후 pending/running 처리 방식 |

권장안: snapshot은 불변으로 유지하고 classification 실행은 별도 이력으로 저장합니다. 같은 snapshot을 재시도하면 새 실행을 만들고 과거 결과를 덮어쓰지 않습니다.

### B-3. 분석 worker 실행 순서 확정

목표 순서를 다음처럼 확정합니다.

```text
InputSnapshot 로드
→ ClassificationInput 생성
→ classification 실행 또는 안전 fallback
→ J10~J12 adapter에 raw clause + 후보 전달
→ R01~R10·J01~J12 규칙 실행
→ RAG
→ 생성·Guardrail
→ 결과 분리 저장
```

B가 반드시 고정할 실패 정책:

- classification 실패가 기존 추출값을 변경하지 않음
- classification 실패가 규칙 상태를 직접 만들지 않음
- 후보가 없으면 J10~J12가 명세에 따라 `확인 필요` 또는 `확인 불가`를 반환
- 규칙 결과가 생성 실패와 분리되듯 classification provider 실패 원인도 구조적으로 기록
- provider 원문 오류·PII를 사용자 응답이나 일반 로그에 그대로 노출하지 않음

### B-4. API 노출 범위 결정

다음 두 방식 중 하나를 C와 합의합니다.

- 권장: classification은 내부 분석 단계로 유지하고 기존 analysis `pending/running/completed/failed` 폴링 계약을 유지
- 대안: `classification_status`, `classification_error`를 분석 상세 응답에 추가

권장안을 선택하면 Frontend에 새 진행 상태를 추가할 필요가 없습니다. classification provider가 실패해도 안전 fallback 후 규칙 분석이 완료되면 분석 전체는 `completed`가 될 수 있습니다.

별도 상태를 노출한다면 다음을 명시해야 합니다.

- nullable 여부와 상태 전이
- Backend `failed`와 classification fallback을 구분하는 코드
- 사용자가 재시도할 대상이 classification인지 전체 분석인지
- 과거 v1.8 응답에서 필드가 없을 때의 처리

### B-5. B가 수정할 예상 파일

A가 새 canonical 타입을 제공한 뒤 다음 파일을 변경합니다.

- `backend/app/models/analysis.py`: classification 실행·결과 저장 모델 또는 AnalysisRun 확장
- `backend/app/workers/analysis.py`: snapshot 이후 classification 실행 순서 연결
- `backend/app/schemas/analysis.py`: 필요한 경우 상태·오류 응답 추가
- `backend/app/api/routes/analyses.py`: 새 저장 결과 조회 연결
- DB migration 파일 또는 팀이 확정한 수동 migration 문서
- `backend/tests/api/test_analyses.py`: 정상·fallback·실패·재조회
- `backend/tests/api/test_case001_e2e.py`: 전체 사용자 흐름
- `backend/tests/workers/test_stale_runs.py`: classification 실행 상태를 노출할 경우 stale 복구

Backend는 `ClassificationInput`·`ClassificationResult` 도메인 타입을 중복 정의하지 않고 A의 canonical Pydantic 타입을 import해야 합니다.

### B 완료 조건

- 기존 v1.8 분석 이력 조회가 깨지지 않음
- 새 snapshot에서 classification 결과와 provenance가 저장·재조회됨
- 재시도 정책과 stale 복구가 테스트됨
- classification 실패에서도 규칙 엔진이 추측하지 않고 명세 상태를 반환함
- Backend가 RuleStatus·urgency를 임의로 만들거나 변경하지 않음
- OpenAPI가 실제 응답과 일치함

---

## C 작업: A 시작 전에 결정할 사항

### C-1. 구 필드 사용 위치 조사 결과 확인

현재 확인된 직접 사용 위치:

- `frontend/src/features/extraction-review/viewModel.ts`
  - `deposit_return_condition` → “보증금 반환 조건”
  - `repair_responsibility` → “수리·원상복구 책임”
- `frontend/src/types/api.ts`
  - `SchemaVersion`이 현재 `"1.8.0"` literal
  - `InputSnapshotDto`와 분석 결과 DTO가 canonical wire 구조를 직접 표현
- `frontend/src/mocks/handlers.ts`와 테스트 fixture
  - InputSnapshot·AnalysisRun 응답을 고정 fixture로 사용

C는 추가 사용 위치가 없는지 확인하고 아래 표를 작성해 A·B에게 전달합니다.

| 구 필드 | 현재 화면 | 새 원문 필드 | 전환 후 처리 |
|---|---|---|---|
| `deposit_return_condition` | 추출 검토 | `deposit_return_clause` | 제거·읽기 호환·숨김 중 선택 |
| `repair_responsibility` | 추출 검토 | `repair_responsibility_clause` | 제거·읽기 호환·숨김 중 선택 |
| 없음 | 추출 검토 | `main_clauses` | 표시명·수정 UI 결정 |
| 없음 | 추출 검토 | `special_clauses` | 표시명·수정 UI 결정 |

### C-2. 사용자 확인 대상 결정

권장 UX:

- 사용자가 확인·수정하는 대상은 계약서에 실제 적힌 조항 원문
- classification의 `clarity_candidate`, `responsible_party_candidate`는 사용자 추출 확인값으로 취급하지 않음
- classification 후보는 규칙 엔진 내부 입력으로 사용하고 추출 검토 화면에서 수정시키지 않음
- 결과 화면에는 기존 J10~J12 판정·이유·질문을 표시하며 모델 후보 자체는 노출하지 않음

C가 답해야 하는 질문:

1. `deposit_return_clause`, `repair_responsibility_clause`, `main_clauses`, `special_clauses`를 추출 검토 화면에서 어떤 순서와 라벨로 표시합니까?
2. 문자열 목록인 본문·특약을 현재 쉼표 기반 입력으로 수정해도 됩니까, 항목별 입력이 필요합니까?
3. 구 필드가 같이 오는 과도기 응답에서 중복 표시를 어떻게 막습니까?
4. 과거 v1.8 분석 이력을 다시 열 때 구 필드를 계속 보여줍니까?

### C-3. 분석 진행·실패 화면 정책 결정

B가 권장안처럼 classification을 내부 단계로 유지하면:

- `AnalysisProgressPage.tsx`의 기존 폴링 계약 유지
- classification fallback은 Backend failed로 표시하지 않음
- 분석이 완료되면 J10~J12의 `확인 필요`·`확인 불가` 결과를 일반 판정처럼 표시

B가 별도 classification 상태를 API에 노출하면 C는 다음을 추가해야 합니다.

- DTO의 nullable status/error
- 진행 문구와 terminal 판단 포함 여부
- classification만 실패한 경우의 배너
- 전체 분석 재실행 또는 기존 실행 재조회 중 재시도 동작

새 상태를 만들기 전에 B와 C가 화면에 실제 가치가 있는지 합의해야 합니다.

### C-4. C가 수정할 예상 파일

A·B의 새 계약이 고정된 뒤 다음 파일을 변경합니다.

- `frontend/src/types/api.ts`: schema version과 새 응답 DTO 동기화
- `frontend/src/features/extraction-review/viewModel.ts`: 구 후보 필드 제거·숨김, 조항 원문 라벨 추가
- `frontend/src/pages/extraction-review/ExtractionReviewPage.tsx`: 조항 원문 확인·수정 UI
- `frontend/src/pages/analysis-progress/AnalysisProgressPage.tsx`: B가 별도 상태를 노출할 때만 변경
- `frontend/src/pages/result-report/ResultReportPage.tsx`: J10~J12 fallback 상태 표시 회귀 확인
- `frontend/src/mocks/handlers.ts`: 실제 `/api` 응답과 동기화
- 관련 Vitest fixture·페이지 테스트
- Playwright 전체 사용자 흐름 E2E

### C 완료 조건

- 추출 검토 화면에서 구 후보 필드와 새 원문 필드가 중복 표시되지 않음
- 사용자가 J10~J12에 필요한 조항 원문을 확인·수정할 수 있음
- classification 후보를 사용자 사실값처럼 수정하거나 저장하지 않음
- 과도기 v1.8 응답과 새 응답 처리 정책이 테스트로 고정됨
- classification fallback에서도 결과 화면이 멈추지 않고 규칙 판정을 표시함
- MSW와 실제 `/api` 경로·응답이 일치함
- Playwright 전체 흐름이 통과함

---

## A를 바로 시작시키기 위한 최소 전달물

B와 C는 아래 내용만 먼저 합의해 전달하면 됩니다.

### B 전달물

```text
1. schema 전환: additive / 즉시 제거
2. 기존 v1.8 snapshot·analysis 이력 처리: 그대로 보존 / migration
3. classification 저장 위치와 연결 키:
4. 재시도 시 새 실행 생성 여부:
5. classification 실패 시 분석 전체 상태:
6. API에 classification 상태 노출 여부:
7. DB migration 방법:
```

### C 전달물

```text
1. 구 필드 두 개의 제거·숨김·읽기 호환 정책:
2. 새 조항 원문 네 필드의 화면 라벨과 표시 순서:
3. main_clauses·special_clauses 수정 UI 방식:
4. 과거 v1.8 이력 표시 정책:
5. 별도 classification 상태 UI 필요 여부:
6. 변경 대상 fixture·E2E 목록:
```

### B·C 공동 전달물

- 새 분석 상세 응답 JSON 예시 1개
- v1.8 → 다음 버전 필드 전환표 1개
- 작업 순서: A schema → B 저장/API → C DTO/UI

이 전달물이 오면 A는 B·C 코드 완료를 기다리지 않고 다음 canonical schema와 classification 실행 구현을 시작할 수 있습니다.
