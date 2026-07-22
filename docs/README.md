# docs/

슬기로운 계약생활의 설계·기획 문서.

## 목적

서비스 개요, 사용자 흐름, PoC·MVP 범위, 아키텍처, API·데이터·AI 설계, 결정 기록, 회의록을 관리한다.

## 하위 구조

```
planning/       service-overview.md user-flow.md poc-scope.md mvp-scope.md
                differentiation.md minimum-mvp-v1.md minimum-mvp-runbook.md
architecture/   system-architecture.md ai-pipeline.md data-flow.md deployment.md
api/            api-overview.md error-format.md
backend/        auth-and-persistence.md
data/           document-fields.md rule-definition.md rag-sources.md privacy-policy.md
                judgment-spec.md training-dataset.md
ai/             extraction-design.md rule-engine-design.md rag-design.md
                prompt-management.md evaluation-plan.md
                local-model-plan.md fine-tuning-plan.md
                model-routing.md evaluation-matrix.md
decisions/      기술·기획 결정 기록
meetings/       회의록
testing/        실제 API·브라우저 통합 검증 실행 절차
```

## 저장해야 하는 파일

- 설계·기획 마크다운 문서, 결정 기록, 회의록

## 저장하면 안 되는 파일

- 실제 개인정보·계약 문서
- 근거 없는 통계·성능 수치·미확정 기술의 임의 확정

## 다른 폴더와의 연결

- 코드 각 폴더(`ai/backend/frontend/data`)의 설계 근거를 제공한다.
- API·데이터 스키마 변경 시 관련 문서를 동기화한다.

## 현재 상태

- 위 지도 문서 전부 작성됨. 미정 항목은 각 문서에서 TODO로 표시.
- 판정 단일 기준: `data/judgment-spec.md`. 모델 라우팅 확정표: `ai/model-routing.md`. 최소 MVP 실행 기준: `planning/minimum-mvp-runbook.md`.
- 계약 연습 실제 API 검증: `testing/practice-real-api-validation.md`. 전용 Playwright spec과 MSW 사전검증은 준비됐으며 실제 API 실행 절차를 설명한다.
