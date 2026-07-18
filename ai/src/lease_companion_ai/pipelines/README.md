# pipelines/

## 책임

개별 AI 모듈을 순서대로 연결한다. PoC 기술 검증과 MVP 사용자 흐름을 혼용하지 않는다.

## 현재 구현

- `minimum_mvp.py`: canonical `InputSnapshot`을 받아 R01~R10과 J01~J12 판정 및 R 규칙 공식 근거 enrichment를 실행한다.
- Backend worker가 이 결과를 저장한 뒤 `GenerationService`와 Guardrail을 실행한다.
- `minimum_mvp.py`는 현재 Backend 실행 경로에서 사용되므로 legacy 이름만 보고 삭제하지 않는다.

## 후속 범위

- J 결과 공식 근거·생성 안내 연결
- 독립 routing·classification 계층 연결
- 외부 embedding·rerank 실행 경로와 fallback 평가 보강

저장과 사용자별 실행 오케스트레이션은 `backend/`가 담당한다.
