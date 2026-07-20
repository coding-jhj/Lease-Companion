# 생성 LLM provider를 Gemini로 통합

- 날짜: 2026-07-20
- 상태: 확정

## 배경

기존 선정표는 구조화·OCR에 Gemini 3.5 Flash, 사용자용 설명·질문·행동 생성과 저신뢰 재검토에 GPT-5.6 Sol을 사용하도록 정했다. 그러나 MVP 단계에서 OpenAI API 비용을 피하고 이미 사용하는 Gemini API로 상용 LLM 연동을 단순화할 필요가 생겼다.

## 결정

- 구조화·OCR뿐 아니라 생성·재검토도 Gemini 3.5 Flash(`gemini-3.5-flash`)를 사용한다.
- 생성 경로는 Google GenAI SDK와 Pydantic Structured Outputs를 사용한다.
- `GEMINI_API_KEY`를 기본 키로 사용하고 `GOOGLE_API_KEY`도 허용한다.
- OpenAI 생성 provider와 OpenAI SDK 의존성은 제거한다.
- 키가 없거나 provider 호출이 실패하면 기존의 결정적 안전 템플릿 fallback을 사용한다.
- Python 규칙 엔진만 `RuleStatus`와 `urgency`를 결정한다. Gemini 생성 결과는 이를 변경할 수 없으며 기존 guardrail과 Pydantic 검증을 그대로 통과해야 한다.
- 실제 외부 API smoke test는 기본 회귀 테스트에서 제외하고, 합성 CASE-001과 명시적 실행 플래그가 있을 때만 수행한다.

이 결정은 2026-07-14 선정표 중 생성·재검토 모델 부분만 대체한다. OCR 통합, 임베딩, 리랭커와 로컬 7B 비교실험 결정은 변경하지 않는다.

## 근거

- OpenAI API 비용을 MVP 크리티컬 패스에서 제거한다.
- 이미 구조화·OCR에 사용하는 Gemini SDK와 키를 재사용해 운영 구성을 단순화한다.
- Gemini 3.5 Flash가 JSON Schema 기반 구조화 출력을 지원해 기존 생성 Pydantic 계약을 유지할 수 있다.

공식 문서:

- [Gemini 3.5 Flash 모델](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash)
- [Gemini API Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output)

## 영향과 보완

- 단일 provider 의존도가 높아지고 서로 다른 모델을 통한 독립 재검토 이점은 줄어든다.
- 이를 Python 규칙 엔진의 판정 권한 고정, Pydantic 출력 검증, 공식 근거 제한, guardrail, 안전 템플릿 fallback과 평가 데이터로 보완한다.
- 무료 할당량과 데이터 이용 조건은 계정·지역·정책에 따라 달라질 수 있다. 실제 사용자 문서로 호출하기 전 비용 및 데이터 처리 정책을 별도로 확인한다.

## 영향받는 영역

- `ai/src/lease_companion_ai/providers/`
- `backend/app/workers/analysis.py`
- AI provider·generation 테스트와 CASE-001 opt-in smoke test
- 모델 라우팅, 배포, API, MVP 범위 문서
