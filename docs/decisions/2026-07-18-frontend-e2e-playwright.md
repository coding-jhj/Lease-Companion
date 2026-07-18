# Frontend E2E 도구 Playwright 결정

- 상태: 확정
- 날짜: 2026-07-18

## 결정

React + Vite 모바일 웹앱의 브라우저 E2E 도구로 Playwright를 사용한다. 첫 검증 범위는 Chromium 모바일 viewport에서 회원가입부터 체크리스트 저장까지의 8단계 사용자 흐름이다.

## 이유

- Vite 개발 서버를 테스트 실행과 함께 자동 기동할 수 있다.
- 모바일 기기 viewport와 접근성 기반 locator를 기본 지원한다.
- 추후 실제 Backend 서버 기반 E2E와 CI 브라우저 매트릭스로 확장할 수 있다.

현재 E2E는 MSW를 실제 API 경로·DTO로 실행해 프론트 전체 흐름을 검증한다. 실제 Backend·DB·파일 저장까지 포함하는 통합 E2E는 별도 실행 프로필로 확장한다.
