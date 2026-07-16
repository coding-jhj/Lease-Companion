# 프론트엔드 기술 스택 결정

- 상태: 확정
- 결정일: 2026-07-16

## 배경

슬기로운 계약생활 MVP는 로그인한 사용자가 계약 건 단위로 문서를 업로드하고, 추출값을 확인·수정하며, 분석 결과와 체크리스트를 저장·재조회하는 모바일 우선 웹앱이다.

현재 우선순위는 검색 유입이나 서버 렌더링이 아니라 로그인 이후의 단계별 상호작용과 FastAPI REST API 연동이다. 프론트엔드가 백엔드 구현을 기다리지 않고 개발될 수 있도록 동일한 요청·응답 계약을 사용하는 mock 경계도 필요하다.

## 검토한 선택지

- React + Vite 기반 SPA
- Next.js 기반 React 애플리케이션
- Vue + Vite 기반 SPA

## 결정

- UI 라이브러리: React
- 언어: TypeScript
- 빌드 도구: Vite
- 애플리케이션 형태: SPA
- 라우팅: React Router
- API 통신: `fetch` 기반 서비스 계층
- API mock: MSW
- 단위·컴포넌트 테스트: Vitest + Testing Library
- 패키지 관리자: npm

프론트엔드 프로젝트는 `frontend/`에서 관리한다.

## 근거

- 로그인 이후 상호작용이 중심인 모바일 웹앱 요구에 SPA가 적합하다.
- Vite는 현재 MVP에 불필요한 서버 렌더링 계층 없이 개발 환경을 구성할 수 있다.
- TypeScript 타입을 FastAPI 요청·응답 스키마와 동기화할 수 있다.
- MSW를 API 경계에 두면 화면·기능 코드를 변경하지 않고 mock 응답을 실제 API로 순차 교체할 수 있다.
- Vitest와 Testing Library로 사용자 흐름과 컴포넌트 상태를 같은 TypeScript 환경에서 검증할 수 있다.

## 구현 규칙

- 페이지와 feature에서 mock 데이터를 직접 가져오지 않는다.
- API 호출은 `src/services`, 백엔드 스키마 대응 타입은 `src/types`에 둔다.
- MSW handler와 실제 API client는 동일한 요청·응답 타입을 사용한다.
- 기준 8단계 사용자 흐름과 모바일 우선 접근성 요구를 유지한다.
- 색상만으로 결과 상태나 확인 우선순위를 표현하지 않는다.

## 미정 사항

- CSS 방식과 UI 컴포넌트 라이브러리
- 인증 라이브러리, 세션·토큰 저장 방식
- 전역 상태 관리 라이브러리 도입 여부
- 배포 플랫폼

위 항목은 구현 필요와 제약이 구체화될 때 별도 결정 기록으로 확정한다.

## 영향

- `frontend/`의 프레임워크 초기화 및 `package.json` 생성 금지를 해제한다.
- 프로젝트 초기화와 화면 구현은 이 결정과 별개의 후속 작업으로 수행한다.
- 전체 MVP API 계약이 확정되기 전에는 API 경계와 mock 계약을 먼저 정의한다.

## 관련 문서

- [`../../AGENTS.md`](../../AGENTS.md)
- [`../PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md)
- [`../../frontend/AGENTS.md`](../../frontend/AGENTS.md)
- [`../../frontend/README.md`](../../frontend/README.md)
