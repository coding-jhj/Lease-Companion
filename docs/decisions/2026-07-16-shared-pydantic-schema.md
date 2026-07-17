# 2026-07-16 — 공통 Pydantic 통합 스키마 (canonical runtime schema)

- **상태**: 확정 (2026-07-16 팀 합의)
- **범위**: AI·Backend·Frontend가 공유하는 런타임 데이터 계약의 단일 원본과 필드 규약. 실제 Pydantic 모델·생성 JSON Schema는 2026-07-16 A 작업에서 구현됐다.

## Canonical runtime schema 위치

```
ai/src/lease_companion_ai/schemas/
```

이 경로의 **Pydantic 모델 하나가 런타임 통합 스키마의 단일 원본(Source of Truth)**이다.

## Pydantic 모델을 단일 원본으로 사용하는 이유

- 현재 스키마가 4계층(JSON 설계 템플릿, AI dataclass·평면 dict, Backend `dict[str, Any]`, goldset 평면 객체)으로 갈라져 있어 3인 분업 시 재통합 비용이 크다.
- Pydantic은 런타임 검증·직렬화·JSON Schema 생성을 한 코드에서 제공하므로, 손으로 유지하는 JSON Schema의 드리프트를 없앤다.
- AI 파이프라인(Python)과 Backend(FastAPI)가 같은 언어이므로 타입을 직접 import해 재사용할 수 있다.

## Backend 재사용 원칙

- Backend는 AI 영역의 공통 도메인 타입을 **import하여 사용**한다.
- Backend에서 같은 도메인 타입을 **중복 정의하지 않는다.** (API 경계 전용 요청·응답 wrapper는 `backend/app/schemas/`에 둘 수 있으나 도메인 필드 정의를 복제하지 않는다.)

## 필드 규약

| 항목 | 규약 |
|------|------|
| 사용자 수정값 | `user_corrected_value` |
| 확인 상태 | `verification_status` |
| 추출 신뢰도(confidence) | 숫자가 아닌 3등급: `추출됨` / `불확실` / `실패` |
| 원문 증거(source evidence) | `page` / `text` 필드. **둘 다 null 허용** (자리는 항상 존재) |

## 식별자 구분

| 식별자 | 의미 |
|--------|------|
| `contract_id` | 실제 사용자 계약 건 (영속 저장의 루트) |
| `case_id` | `CASE-001` 같은 합성·평가 사례 (fixture·goldset 전용) |
| `document_id` | 업로드 문서 |
| `input_snapshot_id` | 사용자 확인 완료 입력의 불변 스냅샷 |
| `analysis_run_id` | 분석 실행 1회 |

**`contract_id`와 `case_id`를 같은 의미로 사용하지 않는다.** 대표 통합 fixture는 `CASE-001`이며 이는 합성 평가 사례이지 실제 사용자 계약 식별자가 아니다.

## 스키마 버전 관리 원칙

- 스키마에 버전 필드를 두고, 필드 추가·의미 변경 시 버전을 올린다.
- 분석 결과에는 사용된 스키마 버전을 기록해 재분석·이력 조회 시 대조할 수 있게 한다.
- 이 결정 당시 구현 버전은 **1.1.0**이었다. R01~R10 결과 역할을 구분하는 `result_type`과 현재 결과의 행동 활성화 여부인 `triggers_actions`를 additive 필드로 추가했다.

### 2026-07-17 구현 부록

- 현재 canonical 버전은 **1.2.0**이다.
- `InputSnapshot.contract_context`와 공개 `GenerationResult`·`RuleGuidance`를 추가했다.
- 기존 스냅샷은 덮어쓰지 않으며 계약 상황 변경 후 재확인으로 새 스냅샷을 생성한다.
- 생성 결과는 `AnalysisRunResult`와 분리하고 `analysis_run_id`·`rule_id`·공식 `source_ids` 연결을 저장 전에 검증한다.

## JSON Schema 생성 원칙

- 배포용 JSON Schema는 손으로 작성하지 않고 **Pydantic 모델에서 생성**한다.
- 생성 산출물은 검증·프론트엔드 타입 동기화용이며, 원본은 항상 Pydantic 모델이다.

## 기존 data/schemas JSON 처리

- `data/schemas/legacy/contract_schema.json` · `registry_schema.json`은 numeric confidence·`user_verified` 등 이 결정과 충돌하는 **legacy/reference 설계 템플릿**이다.
- 삭제·이동·손 재작성하지 않는다. 현행 생성 JSON Schema는 `data/schemas/generated/`에서 관리한다. (`data/schemas/README.md`에 상태 명시)

## R01~R10 우선, J01~J12 후속 확장 시 호환 원칙

- 1차 스키마는 현행 R01~R10 실행에 필요한 필드를 우선 확정한다.
- J01~J12 확장은 **필드 추가**로 진행하고, 기존 R01~R10 필드의 이름·의미를 바꾸지 않는다(하위 호환).
- R과 J는 같은 번호 체계로 합치지 않는다. R 규칙↔J 판정 매핑은 [`../data/judgment-spec.md`](../data/judgment-spec.md)에서 관리한다.

## 관련 결정

- 플랫폼 스택: [`2026-07-16-mvp-platform-stack.md`](2026-07-16-mvp-platform-stack.md)
