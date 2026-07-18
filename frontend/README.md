# frontend/

슬기로운 계약생활의 사용자 화면. **회원·계약 관리를 포함한 모바일 최적화 웹앱**이다. PC 중심이 아니라 모바일 웹앱을 기준으로 설계한다.

> **기술 스택 확정(2026-07-16): React + Vite + TypeScript SPA.** 상위 플랫폼 결정은 [`2026-07-16-mvp-platform-stack.md`](../docs/decisions/2026-07-16-mvp-platform-stack.md), 프론트 구현 상세는 [`2026-07-16-frontend-react-vite.md`](../docs/decisions/2026-07-16-frontend-react-vite.md)를 따른다.

## 기술 스택

- React + Vite + TypeScript SPA
- React Router
- `fetch` 기반 API 서비스 계층
- MSW
- Vitest + Testing Library
- npm

## 목적

로그인한 사용자가 **계약 건 단위**로 계약 문서를 관리한다. 사용자 흐름 8단계를 화면으로 제공하고, AI 추출 결과를 사용자가 확인·수정하게 하며, 분석 결과·체크리스트·계약 직후 행동 상태를 계약 건에 저장하고 재조회한다.

## 사용자 흐름 8단계 ↔ 화면 매핑

| 단계 | 흐름 | 담당 페이지 (`src/pages`) |
|------|------|--------------------------|
| 1 | 회원가입·로그인 | `auth` |
| 2 | 계약 대시보드·계약 건 생성 | `dashboard`, `contract-create` |
| 3 | 계약 상황 입력 | `contract-create` |
| 4 | 계약서·등기 등 문서 업로드 | `document-upload` |
| 5 | 추출값 확인·수정 | `extraction-review` |
| 6 | 분석 (상용 LLM 구조화 → 규칙 엔진 → RAG → 상용 LLM 생성, 로컬 7B는 선택적 성능비교 실험) | `analysis-progress` |
| 7 | 판정·원문 증거·공식 근거·질문·행동 리포트 | `result-report` |
| 8 | 체크리스트·계약 직후 행동 관리 | `contract-detail` |

## 하위 구조

```
public/assets/          정적 에셋
src/
  pages/                화면 단위 (책임: pages/README.md)
  features/             흐름 단계별 기능 모듈 (책임: features/README.md)
  components/           common/ layout/ feedback/ 공통 UI
  services/             API 호출
  types/                백엔드 스키마 대응 타입
  hooks/ utils/ styles/
tests/                  components/ features/ pages/
```

페이지·feature 디렉터리에 실제 코드가 있으며, `.gitkeep`은 빈 디렉터리를 유지할 때만 사용한다.

## 로컬 실행

백엔드를 `http://127.0.0.1:8000`에서 먼저 실행한 뒤 다음 명령을 사용한다. Vite가 `/api` 요청을 백엔드로 프록시한다.

```powershell
cd frontend
npm install
npm run dev
npm test
npm run test:e2e
```

`npm run test:e2e`는 Playwright Chromium 모바일 viewport에서 MSW 기반 8단계 사용자 흐름을 검증한다. 최초 실행 환경에서는 `npx playwright install chromium`이 필요하다.

기본 개발 실행은 실제 API를 사용한다. MSW 기반 test/Story 개발이 필요할 때만 `VITE_ENABLE_MSW=true`를 설정한다.

## 구현 위치

- 화면 컴포넌트 → `src/pages/<page>/`
- 기능 로직·상태·UI → `src/features/<feature>/`
- API 클라이언트 → `src/services`
- 백엔드 스키마 대응 타입 → `src/types`
- 테스트 → `tests/`

## 저장하면 안 되는 파일

- 실제 개인정보·계약 문서
- API 키·비밀정보

## 다른 폴더와의 연결

- `backend/` API를 호출하고 스키마 타입을 동기화한다. (`docs/api/`)

## 현재 상태 / TODO

- React + Vite + TypeScript SPA 초기화와 사용자 흐름 8단계 화면 구현 완료.
- JWT Bearer 로그인, 계약·문서·추출·분석·체크리스트 실제 API 연결 완료. refresh token과 운영 토큰 정책은 Backend TODO를 따른다.
- 추출과 분석은 `pending`·`running`·`completed`·`failed` 상태를 실제 API 폴링으로 처리한다.
- 추출과 분석은 공통 `pollUntilTerminal()`을 사용한다. 로컬 MVP 임시 최대 대기시간은 60초이며, timeout은 Backend `failed`와 구분해 기존 실행 상태를 다시 확인한다. 화면 이탈 시 폴링을 중단한다.
- 분석 규칙 결과와 안내 생성 상태는 분리한다. 안내 생성만 실패하면 규칙 결과를 유지하고 사용자에게 별도 안내를 표시한다.
- 리포트는 canonical v1.8.0 `GenerationResult`의 R/J 설명·질문·서명 전 체크리스트·계약 직후 행동과 안전한 fallback 표시를 제공한다.
- 체크리스트·계약 직후 행동은 안정 `item_key`로 실제 문구와 저장 상태를 결합한다.
- 피드백 등록·이력, 분석 이력, 문서 이력 API를 화면에 연결했다.
- MSW는 실제 API 경로·DTO와 같은 계약을 사용하며, Playwright E2E로 8단계 흐름을 검증한다.
- `src/types`는 현재 Backend 응답과 canonical Pydantic 계약(`user_corrected_value`·`verification_status`·3등급 confidence·nullable `page`/`text`)에 맞춘다.
- 화면 확인 우선순위 3단계(반드시 확인·확인 권장·일반 확인) 매핑과 접근성 원칙은 [`AGENTS.md`](AGENTS.md) 참조
