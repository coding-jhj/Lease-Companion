# providers/

## 책임

외부 제공자(상용 LLM, 임베딩 등) 호출을 어댑터로 감싼다. 나머지 모듈은 제공자 SDK에 직접 의존하지 않고 이 어댑터를 통해 호출한다. 제공자 교체·하이브리드 사용을 국소화한다.

## 하위 구조

- 상용 LLM 어댑터 (구조화·생성·재검토 Gemini 3.5 Flash)
- 임베딩 어댑터 (gemini-embedding-001, RAG 인덱싱·검색용)
- 리랭커 어댑터 (Cohere rerank-v4.0-pro)
- 공통 인터페이스 (키·타임아웃·재시도, 키는 `.env`)

## 입력

- 상위 모듈의 호출 요청 (프롬프트·입력·파라미터)

## 출력

- 제공자 응답을 표준 형식으로 반환 (호출부는 제공자 무관)

## 확정 / TODO

- 변경 확정(2026-07-20): 구조화·생성 Gemini 3.5 Flash · 임베딩 gemini-embedding-001 · 리랭커 Cohere rerank-v4.0-pro. 어댑터로 감싸 호출부는 제공자 무관 유지.
- API 키·비밀정보는 `.env`, Git 커밋 금지
- 구현 완료(배치 1): embedding·rerank `Protocol`, 민감 입력 없는 `ProviderError`, 응답 개수·차원·유한 점수·문서 인덱스 검증, 네트워크 없는 fake provider 테스트.
- 구현 완료(배치 2): `GeminiEmbeddingProvider`와 `CohereRerankProvider`. SDK 예외·응답·입력 원문을 외부 예외 메시지에 노출하지 않는다.
- 구현 완료: `GeminiGateway`가 프로세스 단위 singleton으로 동시 호출·RPM 간격·오류 분류·`Retry-After`·backoff를 관리한다. provider는 자체 재시도 반복문을 갖지 않는다.
- `GeminiGenerationProvider`는 R/J/특약 종류별 배치 Structured Output을 지원한다. 한 분석의 생성 네트워크 호출은 항목 수와 무관하게 최대 3회다.
- 작업별 모델은 `GEMINI_MODEL_PRACTICE`·`GEMINI_MODEL_CLASSIFICATION`·`GEMINI_MODEL_EXTRACTION`·`GEMINI_MODEL_GENERATION`으로 덮어쓸 수 있고 기본값은 기존 확정 모델을 유지한다.
- 로컬 limiter는 `GEMINI_MAX_CONCURRENCY`(기본 1)와 선택적 `GEMINI_REQUESTS_PER_MINUTE`를 사용한다. 여러 프로세스 간 공유 limiter는 제공하지 않는다.
- 특약 생성 요청은 비식별 특약 원문과 허용된 공식 근거만 전달한다. 같은 provider 초안을 설명·확인 질문·수정 요청으로 변환하고 별도 Guardrail을 통과시킨다.
- 구현 완료(classification v1): `ClassificationProvider` Protocol과 결정적 Fake provider, `GeminiClassificationProvider`를 분리했다. Gemini adapter는 `classification-v1` prompt와 canonical `ClassificationInput`·`ClassificationResult`만 사용하며, SDK·원문 오류를 외부 예외에 노출하지 않는다.
- 구현 완료(practice evaluation v1): `GeminiPracticeProvider`가 `practice-evaluation-v1` prompt와 `PracticeTurnEvaluation` Structured Output을 사용한다. R01~R24와 연결된 J 판정은 읽기 전용 요약으로만 전달하며, 최종 상태 전이는 simulation 서비스가 검증한다.
- 계약 연습은 3.5 Flash를 1회 호출하고, 503·timeout일 때만 `GEMINI_MODEL_PRACTICE_FALLBACK`(코드 기본값은 빈 값 = fallback 없음)을 1회 호출한다. 429·인증·요청 오류에는 fallback하지 않으며 한 답변의 실제 호출은 최대 2회다. 2026-07-23 실측에서 `gemini-2.5-flash`·`gemini-2.5-flash-lite`는 현재 키에서 404이므로 fallback 모델로 지정하지 않는다.
- `build_practice_provider()`는 `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY`가 있으면 Gemini, 키가 없고 offline mode면 승인 answer key 기반 Fake, 그 외에는 `None`을 반환한다. 키가 있으면 offline mode보다 Gemini가 우선한다.
- Gemini·Cohere 유료 실호출은 미수행. 키·비용 승인 후 별도 smoke test가 필요하다.
- Gemini 유료 실호출은 미수행. `RUN_GEMINI_GENERATION_SMOKE=1`과 승인된 `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY`가 함께 있을 때만 합성 CASE-001 smoke test가 실행된다.
- 계약 연습 Gemini 실호출은 미수행. `RUN_GEMINI_PRACTICE_SMOKE=1`과 승인된 `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY`가 함께 있을 때만 합성 조건부 반환 smoke test가 실행된다.
