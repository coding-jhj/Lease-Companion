# app/workers/

## 책임

FastAPI `BackgroundTasks`에서 추출과 분석 파이프라인을 실행하고 상태와 결과를 저장한다.

## 현재 동작

- 추출·분석 상태: `pending` → `running` → `completed` 또는 `failed`
- 분석: canonical `InputSnapshot` → classification → R01~R24·J01~J12 → 특약 매칭·공식 근거 RAG → `AnalysisRun.result` 저장 → 생성·Guardrail → `generation_result` 분리 저장
- 특약 결과는 기존 JSON 필드의 `special_clause_reviews`·`special_clause_items`에 저장한다. 별도 테이블·endpoint 없음
- 특약 RAG provider 실패는 빈 `evidence_sources`로 저장한다. R/J 상태·시급도·이유는 바꾸지 않는다
- 생성 실패는 저장된 규칙 결과를 실패로 바꾸지 않는다.
- 서버 기동 시 남은 pending/running 추출·분석·생성 상태를 안전한 실패 상태로 정리한다.
- 상태 조회는 HTTP 폴링을 사용한다.

## TODO

- 운영용 외부 작업 큐
- 재시도·timeout·중복 실행 복구 정책
- 분산 worker 환경의 상태 전달과 관측성
