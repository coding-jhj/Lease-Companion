# frontend/AGENTS.md

`frontend/` 전용 지시서. 루트 [`../AGENTS.md`](../AGENTS.md)를 전제로 하며, 여기서는 프론트엔드 고유 규칙만 정의한다.

## 규칙

- 기준 사용자 흐름 6단계를 유지한다. (`docs/planning/user-flow.md`)
- 사용자가 AI 추출값을 **확인하고 수정**할 수 있도록 설계한다.
- 안전·위험·전세사기를 **단정하는 표현을 쓰지 않는다.** 확인 항목·질문으로 제시한다.
- 로딩 / 오류 / 빈 데이터 / 분석 중 / 분석 완료 상태를 구분해 표시한다.
- API 호출 로직과 UI 컴포넌트를 분리한다. (`src/services` vs `src/components`)
- 모바일과 데스크톱을 함께 고려한다.
- 기본 접근성을 지킨다. (색상만으로 상태를 표현하지 않는 등)
- 백엔드 API 스키마와 프론트엔드 타입(`src/types`)을 동기화한다.

## 미정 — 코드 생성 금지

- 프론트엔드 기술 스택 **미확정.** React·Next.js·Vue 등 프레임워크 코드, `package.json`, 프레임워크 설정을 임의로 생성하지 않는다.
- 스택 확정 전에는 폴더 구조와 이 지시서만 유지한다.

## 폴더 의미 (스택 확정 후 채움)

| 폴더 | 책임 |
|------|------|
| `src/pages` | 화면 단위 |
| `src/features/*` | 흐름 단계별 기능 (contract-stage, document-upload, extraction-review, verification-items, question-cards, signing-checklist, post-contract-actions, result-report) |
| `src/components` | common·layout·feedback 공통 UI |
| `src/services` | API 호출 |
| `src/types` | 백엔드 스키마 대응 타입 |
| `src/hooks` `src/utils` `src/styles` | 훅·유틸·스타일 |
