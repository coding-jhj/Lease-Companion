# docs/

슬기로운 계약생활의 설계·기획 문서.

## 목적

서비스 개요, 사용자 흐름, PoC·MVP 범위, 아키텍처, API·데이터·AI 설계, 결정 기록, 회의록을 관리한다.

## 하위 구조

```
planning/       service-overview.md user-flow.md poc-scope.md mvp-scope.md
architecture/   system-architecture.md ai-pipeline.md data-flow.md deployment.md
api/            api-overview.md error-format.md
backend/        auth-and-persistence.md(예정)
data/           document-fields.md rule-definition.md rag-sources.md privacy-policy.md
                judgment-spec.md(예정) training-dataset.md(예정)
ai/             extraction-design.md rule-engine-design.md rag-design.md
                prompt-management.md evaluation-plan.md
                local-model-plan.md(예정) fine-tuning-plan.md(예정)
                model-routing.md(예정) evaluation-matrix.md(예정)
decisions/      기술·기획 결정 기록
meetings/       회의록
```

`(예정)` 표시 문서는 아직 작성 전이다. 계획된 문서 지도이며 파일 존재를 뜻하지 않는다.

## 저장해야 하는 파일

- 설계·기획 마크다운 문서, 결정 기록, 회의록

## 저장하면 안 되는 파일

- 실제 개인정보·계약 문서
- 근거 없는 통계·성능 수치·미확정 기술의 임의 확정

## 다른 폴더와의 연결

- 코드 각 폴더(`ai/backend/frontend/data`)의 설계 근거를 제공한다.
- API·데이터 스키마 변경 시 관련 문서를 동기화한다.

## 현재 상태

- 초기 설계 문서 작성됨(확정 범위만). 미정 항목은 각 문서에서 TODO로 표시.
