# routing/

## 책임

파이프라인 단계별로 어떤 처리 모델을 쓸지, 실패·저신뢰 시 어디로 넘길지 선택한다. 상용 LLM(Gemini 3.5 Flash 구조화·추출, GPT-5.6 Sol 재검토·생성) 우선 처리, 제공자 장애·할당량 시 fallback 경로를 결정한다. OCR·VLM은 상용 LLM(Gemini 3.5 Flash)에 통합되어 별도 단계가 없다. 로컬 7B는 (선택) 성능비교 실험 경로로만 라우팅한다(MVP 크리티컬 패스 아님). **판정·생성 자체는 하지 않고, 경로만 정한다.**

## 하위 구조

- `models.py` — 처리 단계·primary/fallback 대상·실패 사유·결정 기록 계약
- `service.py` — provider 실행과 fallback 선택·구조화 로그 기록

## 입력

- 단계 식별자 + primary/fallback 대상 + provider 사용 가능 여부 + 실행 함수

## 출력

- 선택 대상, primary 사용 가능 여부, fallback 여부, 실패 사유

## 현재 구현

- 디지털 문서 구조화: Gemini 성공 시 유지, 설정 부재·오류·할당량·응답 검증 실패 시 로컬 정규식 추출
- embedding: Gemini/Chroma 구성·검색 실패 시 BM25
- rerank: Cohere 오류·할당량·응답 검증 실패 시 입력 hybrid 순위 유지
- 실패 사유: `provider_unavailable` · `provider_error` · `quota_exceeded` · `response_validation_failed`
- 모든 결정은 입력 원문이나 provider 예외 원문 없이 `ai_routing_decision` 구조화 로그로 기록한다.

## TODO

- 저신뢰 임계값·재시도·비용 상한은 실제 provider 평가 후 확정한다.
- 생성 provider의 template fallback은 현재 `generation/GenerationService`가 담당한다. 공통 routing 계층 통합은 별도 범위다.
- 로컬 7B는 MVP 크리티컬 패스 제외 상태이므로 routing 대상에 추가하지 않는다.
