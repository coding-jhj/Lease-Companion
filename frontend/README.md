# frontend/

슬기로운 계약생활의 사용자 화면. **회원·계약 관리를 포함한 모바일 최적화 웹앱**이다. PC 중심이 아니라 모바일 웹앱을 기준으로 설계한다.

> **기술 스택 확정.** React + TypeScript + Vite 기반 SPA를 사용한다. 상세 결정은 [`../docs/decisions/2026-07-16-frontend-react-vite.md`](../docs/decisions/2026-07-16-frontend-react-vite.md)를 따른다. 현재는 폴더 구조와 지시서만 존재하며 프로젝트 초기화는 후속 작업이다.

## 기술 스택

- React + TypeScript + Vite
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

각 페이지·feature 디렉터리는 이미 존재하며 현재 `.gitkeep`으로 유지한다. 프로젝트 초기화 시 기존 책임 문서와 사용자 변경사항을 보존한다.

## 구현 위치

- 화면 컴포넌트 → `src/pages/<page>/`
- 기능 로직·상태·UI → `src/features/<feature>/`
- API 클라이언트 → `src/services`
- 백엔드 스키마 대응 타입 → `src/types` (`docs/api/` 확정 후)
- 테스트 → `tests/`

## 저장하면 안 되는 파일

- 실제 개인정보·계약 문서
- API 키·비밀정보

## 다른 폴더와의 연결

- `backend/` API를 호출하고 스키마 타입을 동기화한다. (`docs/api/`)

## 현재 상태 / TODO

- 폴더 구조·지시서만 존재. 화면 미구현.
- **TODO**: 확정 스택으로 프로젝트 초기화·의존성·실행 명령 기록
- **TODO**: 인증 구현 기술·라이브러리 확정 (회원 기능은 MVP 확정, 구현 기술 미정)
- **TODO**: 백엔드 API 확정 후 `src/types` 정의
