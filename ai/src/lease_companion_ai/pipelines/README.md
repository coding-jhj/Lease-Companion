# pipelines/

## 책임

개별 AI 모듈을 순서대로 연결한다. PoC 기술 검증과 MVP 사용자 흐름을 혼용하지 않는다.

## 현재 구현

- Canonical 실행 경로인 `schemas/adapters.py::analyze_snapshot()`이 확인 완료 `InputSnapshot`으로 R01~R10과 J01~J12를 판정하고, R·J 결과에 허용된 공식 근거를 보강한다.
- `classified_analysis.py::analyze_with_classification()`은 `ClassificationService`를 실행한 뒤 검증된 provider 결과 또는 safe fallback을 같은 snapshot의 규칙 분석에 전달한다. 저장·상태 전이·재시도는 포함하지 않는다.
- Backend worker는 확인 완료 snapshot에 `analyze_with_classification()`을 연결해 classification provenance와 canonical 분석 결과를 분리 저장한다. 이어서 `GenerationService`와 Guardrail을 실행하며, 생성은 R·J 결과 모두를 사용하고 규칙 상태·시급도를 변경하지 않는다.
- `minimum_mvp.py`는 추출 데모와 기존 R 결과 반환을 위한 호환 래퍼다. 현재 Backend 분석의 직접 실행 경로는 아니다.

## 후속 범위

- 승인된 실제 Gemini·Cohere provider의 품질·지연시간·비용 기준선 측정
- metadata-only 공식자료 중 이용 가능한 원문 추가 후 R·J 검색 재평가

저장과 사용자별 실행 오케스트레이션은 `backend/`가 담당한다.
