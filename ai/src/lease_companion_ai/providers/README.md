# providers/

## 책임

외부 제공자(상용 LLM, 임베딩 등) 호출을 어댑터로 감싼다. 나머지 모듈은 제공자 SDK에 직접 의존하지 않고 이 어댑터를 통해 호출한다. 제공자 교체·하이브리드 사용을 국소화한다.

## 하위 구조

- 상용 LLM 어댑터 (구조화 Gemini 3.5 Flash / 생성·재검토 GPT-5.6 Sol)
- 임베딩 어댑터 (gemini-embedding-001, RAG 인덱싱·검색용)
- 리랭커 어댑터 (Cohere rerank-v4.0-pro)
- 공통 인터페이스 (키·타임아웃·재시도, 키는 `.env`)

## 입력

- 상위 모듈의 호출 요청 (프롬프트·입력·파라미터)

## 출력

- 제공자 응답을 표준 형식으로 반환 (호출부는 제공자 무관)

## 확정 / TODO

- 확정(2026-07-14 선정표): 구조화 Gemini 3.5 Flash · 생성 GPT-5.6 Sol · 임베딩 gemini-embedding-001 · 리랭커 Cohere rerank-v4.0-pro. 어댑터로 감싸 호출부는 제공자 무관 유지.
- API 키·비밀정보는 `.env`, Git 커밋 금지
- 구현 완료(배치 1): embedding·rerank `Protocol`, 민감 입력 없는 `ProviderError`, 응답 개수·차원·유한 점수·문서 인덱스 검증, 네트워크 없는 fake provider 테스트.
- 구현 완료(배치 2): `GeminiEmbeddingProvider`와 `CohereRerankProvider`. SDK 예외·응답·입력 원문을 외부 예외 메시지에 노출하지 않는다.
- 구현 완료(A10 offline): `OpenAIGenerationProvider`가 Responses API의 `gpt-5.6-sol`과 Pydantic Structured Outputs를 사용한다. SDK는 provider 내부에서만 지연 import하며 timeout 30초·재시도 2회·provider 인스턴스당 최대 10회·응답 1,500토큰을 기본 상한으로 둔다. `store=false`로 호출한다.
- Gemini·Cohere 유료 실호출은 미수행. 키·비용 승인 후 별도 smoke test가 필요하다.
- OpenAI 유료 실호출도 미수행. `RUN_OPENAI_SMOKE=1`과 승인된 `OPENAI_API_KEY`가 함께 있을 때만 합성 CASE-001 smoke test가 실행된다.
