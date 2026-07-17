# generation/

## 책임

규칙 판정과 RAG 근거를 바탕으로 사용자용 산출물을 **생성**한다. 쉬운 설명·확인 질문·서명 전 체크리스트·계약 직후 행동을 만든다. **규칙 판정을 바꾸지 않고, 근거 없는 내용을 만들지 않는다.** 상용 LLM(GPT-5.6 Sol)으로 생성하며 guardrail을 거친다.

## 하위 구조

- `explanations/` — 판정·근거를 임차인이 이해할 쉬운 설명으로 변환
- `questions/` — 임대인·공인중개사 확인 질문, 계약금 입금 전 질문 생성
- `checklists/` — 서명 전 우선 확인·체크리스트 생성
- `actions/` — 계약 직후 권리 확보 행동, 보관 대상(계약서·이체내역·대화 기록) 안내 생성

## 입력

- `rules/` 판정 결과 + 시급도, `rag/` 공식 근거

## 출력

- 판정에 연결된 설명·질문·체크리스트·행동 (생성값, 추출값과 구분)
- 근거 부족 시 확정 표현 없이 확인 필요로 안내

## 구현 상태

- `models.py`: provider 초안은 내부 타입으로 유지하고, 공개 `GenerationResult`·`RuleGuidance`는 `schemas/unified.py` canonical 타입을 재사용
- `service.py`: `triggers_actions=True` 규칙만 생성하며 공식 근거 0건은 provider를 호출하지 않음
- provider 장애·미설정·허용되지 않은 source ID는 항목 단위 결정적 `template_fallback`으로 반환
- 외부 provider 입력은 `guardrails/pii.py`로 토큰화하고, 출력은 로컬 복원 후 금지 단정·grounding·source ID Guardrail을 적용
- 차단된 provider 출력은 안전 템플릿으로 교체한 뒤 다시 검사하며 `guardrail_passed=true` 결과만 반환
- 생성 입력 전후 `AnalysisRunResult` 동일성을 검사하며 규칙 판정 필드를 변경하지 않음
- 실제 provider는 Responses API `gpt-5.6-sol`의 Pydantic Structured Outputs를 사용하며 호출 제한은 provider 내부에 둠
- 공개 Backend·Frontend canonical 타입은 v1.2.0으로 확정. Backend worker 저장 연결과 Frontend 소비는 후속 담당

## 확정 / TODO

- 확정(2026-07-14 선정표): 생성=상용 LLM GPT-5.6 Sol
- 프롬프트 원본은 `ai/prompts/`에서 버전 관리(`docs/ai/prompt-management.md`)
- 정확한 API model ID `gpt-5.6-sol`과 OpenAI Python SDK 2.x 계약을 공식 문서로 확인해 provider를 연결함
- 합성 CASE-001 유료 smoke와 Backend 저장 연결은 각각 키·비용 승인 및 Backend v1.2.0 저장 연결 후 진행
