# app/core/

## 책임

환경 설정, 공통 오류, 비밀번호 해싱과 JWT 보안 유틸 등 애플리케이션 기반 기능을 제공한다. 도메인 로직은 두지 않는다.

## 현재 구현

- `.env` 기반 설정과 필수 비밀값 검증
- PyJWT Bearer access token
- Passlib-bcrypt 비밀번호 해싱
- 공통 오류 형식과 HTTP 예외 처리

오류 형식은 [`docs/api/error-format.md`](../../../docs/api/error-format.md)를 기준으로 한다. refresh token·토큰 폐기·운영 서명 키 관리는 TODO다.
