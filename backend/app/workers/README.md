# app/workers/

## 책임

FastAPI `BackgroundTasks`에서 추출·분석을 실행한다. 선택적 계약 연습 미디어는 웹 요청과 분리한 전용 자식 프로세스에서 실행하고 상태와 결과를 저장한다.

## 현재 동작

- 추출·분석 상태: `pending` → `running` → `completed` 또는 `failed`
- 분석: canonical `InputSnapshot` → classification → R01~R24·J01~J13 → 특약 매칭·공식 근거 RAG → `AnalysisRun.result` 저장 → 생성·Guardrail → `generation_result` 분리 저장
- 특약 결과는 기존 JSON 필드의 `special_clause_reviews`·`special_clause_items`에 저장한다. 별도 테이블·endpoint 없음
- 특약 RAG provider 실패는 빈 `evidence_sources`로 저장한다. R/J 상태·시급도·이유는 바꾸지 않는다
- 생성 실패는 저장된 규칙 결과를 실패로 바꾸지 않는다.
- 생성은 R/J/특약 종류별 최대 3개 Gemini 배치로 실행한다. 배치 일부 누락·검증 실패는 해당 안내만 template fallback으로 저장한다.
- 서버 기동 시 남은 pending/running 추출·분석·생성 상태를 안전한 실패 상태로 정리한다.
- 상태 조회는 HTTP 폴링을 사용한다.
- 계약 연습 미디어는 `queued → generating_audio → generating_video → completed/failed`로 진행한다.
- TURN 응답은 worker 완료를 기다리지 않고 텍스트와 `queued` 상태를 즉시 반환한다. GPU 작업은 프로세스 간 파일 잠금으로 한 번에 하나씩 실행한다.
- Supertonic 3 음성합성과 MuseTalk 1.5 립싱크는 판정·답변 저장과 분리한다. 미디어 실패는 사용자 오답이나 TURN 실패로 바꾸지 않는다.
- 로컬 생성물은 `backend/var/practice-media/` 아래에 저장하며 Git에 포함하지 않는다.

## TODO

- 운영용 외부 작업 큐
- MuseTalk 모델 상주·avatar 전처리 cache를 사용하는 GPU worker
- 운영 미디어 저장소·수명·정리 정책
- 분산 worker 환경의 공유 rate limiter·중복 실행 복구 정책
- 분산 worker 환경의 상태 전달과 관측성
