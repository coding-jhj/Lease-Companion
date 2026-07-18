# B·C 공동 전달물 (BC_HANDOFF.md 응답)

작성: B·C 합의 초안 (2026-07-18)

## 전제 (합의 완료 사항)

- B-4: classification 상태 **API 미노출** 채택. 기존 analysis `pending/running/completed/failed` 폴링 계약 유지.
- schema 전환: **additive**. 구 필드는 한 버전 동안 유지(deprecated), 제거는 그다음 버전에서 별도 ADR로 결정.
- classification 결과는 Backend 내부 저장(AnalysisRun 행)만 하고 응답에 노출하지 않음.
- 기존 v1.8 snapshot·분석 이력은 불변 보존, migration 없음.

## 1. 새 분석 상세 응답 JSON 예시

`GET /api/contracts/{contract_id}/analysis-runs/{analysis_run_id}`

**wire 구조는 v1.8과 동일** — 새 필드 없음. 변경은 payload 내부 schema_version과
extraction 필드 구성뿐.

```json
{
  "analysis_run_id": "AR-20260718-0001",
  "input_snapshot_id": "IS-20260718-0001",
  "status": "completed",
  "error": null,
  "created_at": "2026-07-18T10:00:00+09:00",
  "result": {
    "schema_version": "1.9.0",
    "analysis_run_id": "AR-20260718-0001",
    "input_snapshot_id": "IS-20260718-0001",
    "judgments": [
      {
        "judgment_id": "J10",
        "status": "불명확",
        "urgency": "계약 전 확인",
        "reason": "보증금 반환 시점·조건이 조항에 구체적으로 기재되지 않았습니다.",
        "evidence_sources": []
      },
      {
        "judgment_id": "J11",
        "status": "확인 필요",
        "urgency": "계약 전 확인",
        "reason": "수리·원상복구 책임 주체를 확인할 수 없습니다.",
        "evidence_sources": []
      }
    ]
  },
  "generation_result": { "...": "GenerationResult JSON — v1.8과 동일 구조" },
  "generation_status": "completed",
  "generation_error": null
}
```

- `schema_version` `"1.9.0"`은 자리표시자 — 실제 버전은 A가 확정.
- classification fallback이 발생해도 이 응답 형태는 동일: J10~J12가
  `확인 필요`/`확인 불가` 상태로 내려올 뿐, 별도 상태 필드 없음.
- 과거 v1.8 실행 조회 시에도 같은 wire 구조 (payload 내부 schema_version만 "1.8.0").

## 2. v1.8 → 다음 버전 필드 전환표

대상: `DocumentExtraction`(contract) — 추출 API `contract_doc`·snapshot payload 공통.

| 필드 | v1.8.0 | 다음 버전 | 그다음 버전 | Frontend 처리 |
|---|---|---|---|---|
| `deposit_return_condition` | 존재 (Gemini 해석 후보) | **유지 (deprecated, 읽기 호환)** | 제거 | 추출 검토 화면에서 숨김. 과거 v1.8 이력 조회 시에만 표시 |
| `repair_responsibility` | 존재 (Gemini 해석 후보) | **유지 (deprecated, 읽기 호환)** | 제거 | 상동 |
| `deposit_return_clause` | 존재 | 유지 | 유지 | 사용자 확인·수정 대상 (라벨·순서는 C 전달물) |
| `repair_responsibility_clause` | 존재 | 유지 | 유지 | 상동 |
| `main_clauses` | 존재 | 유지 | 유지 | 상동 |
| `special_clauses_present` / `special_clauses` | 존재 | 유지 | 유지 | 상동 |
| `ClassificationInput` / `ClassificationResult` | 없음 | **신규 (내부 전용)** | 유지 | API 미노출 — Frontend 변경 없음 |

- deprecated 기간 동안 Gemini extraction이 구 필드를 계속 채울지, null로 채울지는 A 결정
  (Frontend는 어느 쪽이든 숨김 처리라 무관).

## 3. 작업 순서 (합의)

A canonical schema(다음 버전) → B 저장·worker 연결 → C DTO·화면·MSW·E2E 전환

## 4. A에게 확인 질문

1. **구 필드 2개가 R 규칙 필수 필드에도 포함됨** — `unified.py`의
   `REQUIRED_CONTRACT_FIELDS`에 `deposit_return_condition`·`repair_responsibility`가
   있고 R 규칙 입력 타입 검증에도 걸려 있음. 제거 버전에서 R 규칙 입력도
   조항 원문+classification 후보 기반으로 바뀌는지, R 필수 필드 목록이 함께
   갱신되는지 확인 필요.
2. deprecated 기간의 구 필드 값 정책 (계속 채움 vs null 고정) — 위 전환표 참조.
