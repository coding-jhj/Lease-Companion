# ai/

슬기로운 계약생활의 AI 처리 계층. Python 패키지 `lease_companion_ai`.

## 목적

계약 문서에서 정보를 추출·정규화하고, 규칙 엔진으로 확인 필요 항목을 분류하며, 공식 자료 RAG로 근거를 찾아 질문·체크리스트·행동·요약을 생성한다.

## 담당 기능

- 멀티모달 LLM 문서 정보 추출
- 주소·금액·날짜·이름 정규화
- Python 규칙 엔진 (계약서·등기사항증명서·건축물대장 비교)
- 공식 자료 RAG
- 질문·서명 전 체크리스트·계약 직후 행동·결과 요약 생성
- Guardrail (단정 표현 제한)
- AI 입출력 스키마, AI 평가

## 하위 구조

```
src/lease_companion_ai/
  extraction/     문서 핵심 필드 추출
  normalization/  추출값 정규화
  rules/          문서 비교·확인 항목 분류
  rag/            공식 근거 검색
  generation/     질문·체크리스트·행동·요약 생성
  guardrails/     단정 표현·잘못된 출력 제한
  pipelines/      PoC·MVP 흐름 연결
  schemas/        AI 입출력 구조
prompts/          extraction/questions/checklists/summaries 프롬프트 원본
tests/            기능별 평가·테스트
```

## 저장해야 하는 파일

- AI 로직 코드, 프롬프트 원본, AI 입출력 스키마, 평가·테스트 코드

## 저장하면 안 되는 파일

- 실제 계약서·개인정보 (→ 절대 금지)
- LLM API 키·비밀정보 (→ `.env`)
- 대용량 벡터 인덱스·모델 가중치 (→ Git 제외)
- 백엔드 API 라우팅·서비스 코드 (→ `backend/`)

## 다른 폴더와의 연결

- `backend/`가 이 패키지의 파이프라인을 호출한다. AI 로직을 backend에 중복 구현하지 않는다.
- 분석 기준·평가 데이터는 `data/`에서 참조한다.
- 설계 문서는 `docs/ai/`.

## 현재 상태 / TODO

- 패키지 스캐폴딩만 존재. 모듈 구현 없음.
- TODO: LLM 제공자·모델 확정 → extraction 구현
- TODO: 임베딩·벡터 저장소 확정 → rag 구현
- TODO: 규칙 스키마 확정(`docs/data/rule-definition.md`) → rules 구현
- TODO: 의존성·실행 방식 확정 후 `pyproject.toml` 갱신
