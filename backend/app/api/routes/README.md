# app/api/routes/

## 책임

FastAPI HTTP 엔드포인트 계층. 요청·응답, 인증·소유권, 입력·업로드 검증, 공통 오류 형식을 처리한다.

현재 로컬 MVP는 일부 흐름과 SQLAlchemy 세션 작업을 라우트에서 직접 수행한다. 장기 목표는 공통 비즈니스 로직을 `services/`, DB 접근을 `repositories/`로 옮기는 것이지만 이번 정리에서는 동작을 변경하지 않는다.

## 구현 영역

- `auth`: 회원가입·로그인·현재 사용자
- `contracts`: 계약 생성·목록·상세·상황 입력·삭제
- `documents`: 업로드·목록·모의 등기 연결
- `extractions`: 시작·폴링·수정·확인
- `analyses`: 실행·이력·상세 폴링
- `checklists`: 체크리스트·계약 직후 행동 상태
- `feedback`: 사용자 피드백 이력

정확한 경로·메서드·요청·응답은 [`docs/api/openapi.json`](../../../../docs/api/openapi.json)을 기준으로 한다. 현재 로컬 비동기 상태 전달은 HTTP 폴링이다.
