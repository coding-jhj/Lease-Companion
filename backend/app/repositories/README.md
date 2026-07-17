# app/repositories/

## 목표 책임

계약 건(`contract_id`) 단위 DB 접근을 캡슐화하고 서비스 계층에 저장소 인터페이스를 제공한다.

## 현재 상태

SQLAlchemy 영속 모델은 `app/models/`에 구현돼 있지만 별도 repository 계층은 아직 구현하지 않았다. 현재 로컬 MVP는 라우트와 워커가 DB 세션을 직접 사용한다.

repository 도입은 동작을 바꾸는 리팩터링이므로 이번 문서·폴더 정리 범위에서는 구현하지 않는다.
