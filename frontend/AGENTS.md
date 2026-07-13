# frontend/AGENTS.md

`frontend/` 전용 지시서. 루트 [`../AGENTS.md`](../AGENTS.md)를 전제로 하며, 여기서는 프론트엔드 고유 규칙만 정의한다.

`frontend/`는 **회원·계약 관리를 포함한 모바일 최적화 웹앱**이다. 단일 세션 6단계 구조가 아니라, 로그인 사용자가 **계약 건 단위**로 관리하는 8단계 흐름을 화면으로 제공한다.

## 규칙

- 기준 사용자 흐름 8단계를 유지한다. (`docs/planning/user-flow.md`)
- 모바일 웹앱을 기준으로 설계한다. PC 중심 아님 — 모바일 최적화 우선.
- 사용자가 AI 추출값을 **확인하고 수정**할 수 있도록 설계한다. (분석 전 확인·수정)
- 안전·위험·전세사기를 **단정하는 표현을 쓰지 않는다.** `안전`/`위험`/`사기 가능성 점수` 같은 종합 판정을 표시하지 않는다. 확인 항목·질문으로 제시한다.
- 결과는 공통 결과 상태 9개(`일치`·`불일치`·`명확`·`불명확`·`미기재`·`상충 가능`·`확인 필요`·`확인 불가`·`적용 제외`)와 시급도 5개(`즉시 확인`·`계약 전 확인`·`계약 직후 조치`·`참고`·`분석 불가`)로 표현한다.
- 로딩 / 오류 / 빈 데이터 / 분석 중 / 분석 완료 상태를 구분해 표시한다.
- API 호출 로직과 UI 컴포넌트를 분리한다. (`src/services` vs `src/components`)
- 기본 접근성을 지킨다. (색상만으로 상태를 표현하지 않는 등)
- 백엔드 API 스키마와 프론트엔드 타입(`src/types`)을 동기화한다.

## 미정 — 코드 생성 금지 (TODO)

- 프론트엔드 기술 스택 **미확정.** React·Next.js·Vue 등 프레임워크 코드, `package.json`, 프레임워크 설정을 임의로 생성하지 않는다.
- 인증 방식 구현 기술·라이브러리 **미확정.** (회원 기능은 MVP 확정, 구현 기술 미정)
- 스택 확정 전에는 폴더 구조와 이 지시서만 유지한다. 각 디렉터리의 `.gitkeep`을 삭제하지 않는다.

## 페이지 책임 (`src/pages/*`, 스택 확정 후 채움)

| 페이지 | 흐름 단계 | 책임 |
|--------|-----------|------|
| `auth` | 1 | 회원가입·로그인 |
| `dashboard` | 2 | 계약 대시보드, 계약 건 목록·생성 진입 |
| `contract-create` | 2·3 | 계약 건 생성, 계약 상황 입력 |
| `document-upload` | 4 | 계약서·등기 등 문서 업로드 |
| `extraction-review` | 5 | AI 추출값 확인·수정 |
| `analysis-progress` | 6 | 분석 진행 상태 표시 |
| `result-report` | 7 | 판정·원문 증거·공식 근거·질문·행동 리포트 |
| `contract-detail` | 8 | 계약 건 상세, 저장된 체크리스트·계약 직후 행동 관리 |

세부 목록은 [`src/pages/README.md`](src/pages/README.md).

## Feature 책임 (`src/features/*`, 스택 확정 후 채움)

`auth`, `contracts`, `contract-stage`, `document-upload`, `extraction-review`, `judgment-results`, `evidence-sources`, `question-cards`, `signing-checklist`, `post-contract-actions`, `result-feedback`.

기존 `verification-items`, `result-report` feature 디렉터리는 유지하되 최신 목록과의 관계는 [`src/features/README.md`](src/features/README.md) 참조. **임의로 삭제하지 않는다.**

## 그 외 폴더 의미

| 폴더 | 책임 |
|------|------|
| `src/components` | common·layout·feedback 공통 UI |
| `src/services` | API 호출 |
| `src/types` | 백엔드 스키마 대응 타입 |
| `src/hooks` `src/utils` `src/styles` | 훅·유틸·스타일 |
