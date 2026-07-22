# generation/

## 책임

규칙 판정과 RAG 근거를 바탕으로 사용자용 산출물을 **생성**한다. 쉬운 설명·확인 질문·서명 전 체크리스트·계약 직후 행동을 만든다. **규칙 판정을 바꾸지 않고, 근거 없는 내용을 만들지 않는다.** 상용 LLM(Gemini 3.5 Flash)으로 생성하며 guardrail을 거친다.

## 구현 파일

- `models.py` — provider 내부 생성 요청 타입
- `service.py` — R/J·특약 안내 생성, 결정적 fallback, stage guidance 조합과 guardrail 적용
- `../providers/gemini_generation.py` — Gemini 3.5 Flash Structured Outputs 어댑터
- `../../../prompts/special_clause_guidance_v1.txt` — 특약 설명·질문·수정 요청 전용 프롬프트
- `../../../prompts/` — 설명·질문·체크리스트·행동 프롬프트 원본과 버전

## 입력

- `rules/` R/J 판정 결과 + 시급도, `rag/` 공식 근거, immutable `ContractContext`

## 출력

- 판정에 연결된 설명·질문·체크리스트·행동 (생성값, 추출값과 구분)
- 근거 부족 시 확정 표현 없이 확인 필요로 안내
- 특약별 쉬운 설명·확인 질문·수정 요청과 사용한 공식 source ID

## 구현 상태

- `models.py`: provider 초안은 내부 타입으로 유지하고, 공개 `GenerationResult`·`RuleGuidance`·`JudgmentGuidance`는 `schemas/unified.py` canonical 타입을 재사용
- `service.py`: `triggers_actions=True`인 R 규칙과 J 판정을 별도 목록으로 생성하며 공식 근거 0건은 provider를 호출하지 않음
- `SpecialClauseReview`마다 비식별 원문과 카드 근거를 사용해 `special_clause_items`를 생성함
- 특약 근거가 없으면 provider를 호출하지 않고 “공식 근거를 확인하지 못했습니다” 한계와 확인 질문만 반환함. 확정 수정 문구는 만들지 않음
- 특약 provider 실패·금지 표현·허용되지 않은 source ID는 공식 근거 범위의 결정적 fallback으로 교체함
- provider 장애·미설정·허용되지 않은 source ID는 항목 단위 결정적 `template_fallback`으로 반환
- 외부 provider 입력은 `guardrails/pii.py`로 토큰화하고, 출력은 로컬 복원 후 금지 단정·grounding·source ID Guardrail을 적용
- 차단된 provider 출력은 안전 템플릿으로 교체한 뒤 다시 검사하며 `guardrail_passed=true` 결과만 반환
- 생성 입력 전후 `AnalysisRunResult` 동일성을 검사하며 규칙 판정 필드를 변경하지 않음
- `StageGuidance`는 `contract_stage`·`deposit_paid`·`signed`·입주일·잔금일과 J 결과를 결합해 입금 전 질문·서명 전 체크리스트·계약 직후 행동·보관 대상을 결정론적으로 생성
- 실제 provider는 Gemini API `gemini-3.5-flash`의 Pydantic Structured Outputs를 사용하며 호출 제한은 provider 내부에 둠
- 공개 생성 타입은 canonical v1.9.0의 `GenerationResult`·`RuleGuidance`·`JudgmentGuidance`·`SpecialClauseGuidance`·`GuidanceActionItem`·`StageGuidance`다. R 안내 `items`, J 안내 `judgment_items`, 특약 안내 `special_clause_items`는 별도 축이다. 세 축 모두 grounding·금지 단정·안전 fallback을 통과한다. `GenerationResult.prompt_version`은 실행에 사용한 prompt set 버전을 기록하고 provider 요청에도 같은 값을 전달한다. Backend worker는 규칙 결과와 생성 결과를 분리 저장한다.

## 확정 / TODO

- 변경 확정(2026-07-20): 생성=상용 LLM Gemini 3.5 Flash
- 프롬프트 원본은 `ai/prompts/`에서 버전 관리(`docs/ai/prompt-management.md`)
- API model ID `gemini-3.5-flash`와 Google GenAI SDK의 구조화 출력 계약을 공식 문서로 확인해 provider를 연결함
- 합성 CASE-001 유료 smoke는 키·비용 승인 후 진행. Backend canonical 저장 연결은 완료됐다.
