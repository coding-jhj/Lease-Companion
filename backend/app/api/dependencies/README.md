# app/api/dependencies/

## 책임

FastAPI 요청 의존성 주입 계층. 라우트가 공통으로 필요로 하는 값을 생성·검증해 제공한다.
현재 요청 사용자(인증 주체) 확인, DB 세션·저장소 핸들 제공, 공통 입력 검증 등.
비즈니스 로직은 두지 않는다.

## 입출력

- 입력: HTTP 요청 컨텍스트(헤더·토큰·쿠키 등)
- 출력: 인증된 `User` 주체, DB 세션/저장소 인스턴스, 검증된 공통 파라미터
- 실패 시: 인증·권한·검증 오류를 공통 오류 형식으로 반환

## 확정 / TODO

- 확정·구현(2026-07-16): 인증 **JWT Bearer(PyJWT) + Passlib-bcrypt**, Access Token 24시간 임시값, DB **PostgreSQL** (→ [`../../../../docs/decisions/2026-07-16-mvp-platform-stack.md`](../../../../docs/decisions/2026-07-16-mvp-platform-stack.md))
- 구현: 현재 사용자 의존성과 PostgreSQL 세션 주입
- 계약 건 소유권 확인은 현재 라우트 공통 함수 `_get_owned_contract` 패턴으로 수행한다. 재사용 범위가 넓어지면 공통 의존성으로 이동한다.
