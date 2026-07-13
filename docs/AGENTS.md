# docs/AGENTS.md

`docs/` 전용 지시서. 루트 [`../AGENTS.md`](../AGENTS.md)를 전제로 하며, 여기서는 문서 고유 규칙만 정의한다.

## 규칙

- 서비스명은 **‘슬기로운 계약생활’**로 통일한다.
- 공식 명칭이 필요한 경우 **‘등기사항증명서’**를 사용한다. (‘등기부등본’ 등 혼용 금지)
- PoC와 MVP 범위를 명확히 구분하고 혼용하지 않는다.
- 검증된 사실 / 기획상 결정 / 합리적 가정 / 미정 사항을 구분해 표기한다.
- 근거 없는 통계·기능·테스트 결과를 작성하지 않는다.
- API·데이터 스키마 변경 시 관련 문서를 동기화한다.
- 회의록에는 결정사항·미결사항·담당자·기한을 기록한다.
- 코드에 구현되지 않은 기능을 구현 완료로 표현하지 않는다.
- 미정 기술(모델·DB·벡터 저장소·성능 수치)은 임의로 확정하지 않고 `TODO`로 둔다.

## 문서 지도

- `planning/` — service-overview, user-flow, poc-scope, mvp-scope
- `architecture/` — system-architecture, ai-pipeline, data-flow, deployment
- `api/` — api-overview, error-format
- `backend/` — auth-and-persistence
- `data/` — document-fields, judgment-spec, rule-definition, rag-sources, privacy-policy, training-dataset
- `ai/` — extraction-design, rule-engine-design, rag-design, prompt-management, evaluation-plan, local-model-plan, fine-tuning-plan, model-routing, evaluation-matrix
- `decisions/` — 기술·기획 결정 기록
- `meetings/` — 회의록
