# app/api/routes/

## 책임

HTTP 엔드포인트 계층. 요청·응답 처리, 입력·업로드 파일 검증, 공통 오류 형식 반환.
비즈니스 로직·AI 호출·저장은 하지 않는다. `services/`에 위임한다.

## API 책임 영역

`auth` · `users` · `contracts` · `documents` · `extractions` · `analyses` · `results` · `checklists` · `feedback`

## 입출력

- 입력: HTTP 요청(경로·쿼리·본문·업로드 파일), 의존성 주입값(`api/dependencies/`)
- 출력: 검증된 요청을 서비스에 전달, 서비스 결과를 응답 스키마(`schemas/`)로 반환
- 오류: 공통 오류 형식 ([`docs/api/error-format.md`](../../../../docs/api/error-format.md))

## TODO (미정)

- 실제 경로·HTTP 메서드·요청/응답 스키마 (확정 전 [`docs/api/api-overview.md`](../../../../docs/api/api-overview.md))
- 인증 방식 확정 후 `auth` 라우트 구현
- 비동기 분석 상태 전달 방식(폴링 vs 콜백)
