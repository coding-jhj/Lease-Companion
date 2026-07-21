# 프롬프트 관리

## 원칙

- 프롬프트를 코드에 길게 하드코딩하지 않는다. 원본은 `ai/prompts/`에 둔다.
- 용도별로 분리한다: `extraction/` `classification/` `questions/` `checklists/` `summaries/`.
- 프롬프트를 버전으로 관리한다.
- 프롬프트 변경 시 버전과 **평가 결과**를 함께 확인한다. (`evaluation-plan.md`, `evaluation-matrix.md`)
- Guardrail을 통과한 출력만 저장한다.

## 적용 대상

- **추출 (`extraction`)**: 상용 LLM(Gemini 3.5 Flash) 필드 구조화 프롬프트. 구조화 출력 스키마와 연동한다.
- **분류 (`classification`)**: 사용자 확인 조항의 유형·명확성·책임 주체·조건 후보 구조화 프롬프트. 최종 판정 필드는 포함하지 않는다.
- **생성 (`generation`)**: 쉬운 설명·질문·체크리스트·행동 프롬프트. 상용 LLM 호출용.
- **재검토 (`routing`→`providers`)**: 저신뢰 결과 재검토 프롬프트.
- **(선택 실험)** 로컬 7B(`local_model`)의 조항 분류 입출력 형식은 파인튜닝 과제 정의를 따르며, 프롬프트 원본과 별도로 관리한다. 로컬 7B는 MVP 크리티컬 패스에서 제외되어(선정표) 성능비교 실험 시에만 적용된다. (`fine-tuning-plan.md`)

## 구조 (권장)

- 프롬프트마다 버전 식별자와 변경 이력을 남긴다.
- 추출·생성 프롬프트는 구조화 출력 스키마(`ai/src/lease_companion_ai/schemas/`)와 연동한다.
- 신규 생성은 `questions/checklists/summaries/v2.txt`를 사용한다. `GenerationResult.prompt_version`은 과거 저장 결과의 `v1` 읽기 호환과 신규 `v2`를 모두 허용하며, 파일 본문에도 용도별 버전 식별자를 기록한다.
- 생성 provider 입력은 로컬 PII 토큰화 후 전송한다. 출력은 로컬 복원 후 금지 단정·근거·source ID Guardrail을 통과해야 저장 대상이 된다.
- canonical v1.6.0부터 prompt set 버전을 provider 요청과 `GenerationResult.prompt_version`에 동일하게 기록한다. 파일 첫 줄의 `버전: {용도}-{버전}`이 설정 버전과 다르면 생성 서비스 시작을 거부한다.

## 미정 (TODO)

- 전체 프롬프트 공통 파일 포맷·버전 승격 규칙과 템플릿 변수 관리 방식
