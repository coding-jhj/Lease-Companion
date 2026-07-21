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
- 백엔드 API 스키마와 프론트엔드 타입(`src/types`)을 동기화한다. Backend/OpenAPI 스키마가 타입의 원천이며, **mock 데이터와 실제 API 응답은 같은 타입을 사용한다** — mock으로 먼저 개발해도 연결 시 타입이 달라지지 않게 한다.
- 추출값 확인·수정 화면의 데이터 형태는 canonical Pydantic 스키마 계약을 따른다. (`user_corrected_value`·`verification_status`·3등급 confidence·nullable `page`/`text` → [`../docs/decisions/2026-07-16-shared-pydantic-schema.md`](../docs/decisions/2026-07-16-shared-pydantic-schema.md))
- **화면 확인 우선순위 3단계 매핑**(사용자 화면 전용 — 내부 상태 9개·시급도 5개를 대체하지 않음): `즉시 확인`·`분석 불가` → **반드시 확인** / `계약 전 확인`·`계약 직후 조치` → **확인 권장** / `참고` → **일반 확인**. 색상만이 아니라 문구·아이콘을 함께 제공한다.

## 기술 스택 (2026-07-16 확정)

- **React + Vite + TypeScript SPA.** 상위 플랫폼 결정은 [`2026-07-16-mvp-platform-stack.md`](../docs/decisions/2026-07-16-mvp-platform-stack.md), 프론트 구현 상세는 [`2026-07-16-frontend-react-vite.md`](../docs/decisions/2026-07-16-frontend-react-vite.md)를 따른다.
- 라우팅은 React Router를 사용한다.
- API 통신은 `fetch` 기반 서비스 계층으로 캡슐화한다.
- API mock은 MSW를 사용하며 페이지·feature가 mock 데이터를 직접 가져오지 않게 한다.
- 단위·컴포넌트 테스트는 Vitest + Testing Library를 사용한다.
- 패키지 관리자는 npm을 사용한다.
- 인증 방식은 JWT Bearer로 확정. 프론트는 토큰 보관·첨부 방식만 다루고 구체 정책(만료·refresh)은 Backend TODO를 따른다.
- CSS 방식·UI 컴포넌트 라이브러리와 전역 상태 관리 라이브러리는 미정이며 별도 결정 없이 추가하지 않는다.
- React + Vite + TypeScript 프로젝트 초기화와 기본 의존성 설치는 완료됐다.
- `.gitkeep`은 실제 추적 파일이 없는 빈 디렉터리를 유지할 때만 둔다.

## 페이지 책임 (`src/pages/*`)

| 페이지 | 흐름 단계 | 책임 |
|--------|-----------|------|
| `auth` | 1 | 회원가입·로그인 |
| `dashboard` | 2 | 계약 대시보드, 계약 건 목록·생성 진입 |
| `contract-create` | 2·3 | 계약 건 생성, 계약 상황 입력 |
| `document-upload` | 4 | 계약서·등기 등 문서 업로드 |
| `extraction-review` | 5 | AI 추출값 확인·수정 |
| `analysis-progress` | 6 | 분석 진행 상태 표시 |
| `result-report` | 7 | 판정·원문 증거·공식 근거·피해 유형 비교·질문·수정 요청·단계별 행동·전체 PDF 리포트 |
| `contract-detail` | 8 | 계약 건 상세, 저장된 체크리스트·계약 직후 행동 관리 |

세부 목록은 [`src/pages/README.md`](src/pages/README.md).

## Feature 책임 (`src/features/*`)

`auth`, `contracts`, `contract-stage`, `document-upload`, `extraction-review`, `judgment-results`, `evidence-sources`, `question-cards`, `signing-checklist`, `post-contract-actions`, `result-feedback`.

기존 `verification-items`, `result-report` feature 디렉터리는 유지하되 최신 목록과의 관계는 [`src/features/README.md`](src/features/README.md) 참조. **임의로 삭제하지 않는다.**

## 그 외 폴더 의미

| 폴더 | 책임 |
|------|------|
| `src/components` | common·layout·feedback 공통 UI |
| `src/services` | API 호출 |
| `src/types` | 백엔드 스키마 대응 타입 |
| `src/hooks` `src/utils` `src/styles` | 훅·유틸·스타일 |
