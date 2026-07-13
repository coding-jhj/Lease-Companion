# backend/

슬기로운 계약생활의 API 서버. **FastAPI** (Python).

## 목적

프론트엔드 요청을 받아 계약 분석 세션을 관리하고, 업로드 파일을 검증하며, `ai/` 파이프라인을 호출하고, 분석 상태·결과를 저장·조회한다.

## 담당 기능

- 계약 단계 입력
- 계약 분석 세션 관리
- 문서 업로드, 파일 형식·크기 검증
- AI 파이프라인 호출
- 분석 상태 관리
- 분석 결과 저장·조회
- 결과 리포트 API
- 공통 오류 처리

## 하위 구조

```
app/
  main.py         FastAPI 진입점
  api/routes/     엔드포인트 (요청·응답, 검증)
  services/       분석 흐름 오케스트레이션 (ai/ 호출)
  repositories/   세션·결과 영속화 (DB 확정 전 경계)
  schemas/        요청·응답 Pydantic 모델
  models/         도메인/영속 모델 (DB 확정 후)
  core/           설정·공통 오류·의존성
tests/            api/services/repositories 테스트
```

## 저장해야 하는 파일

- FastAPI 라우팅·서비스·저장소·스키마 코드, 백엔드 테스트

## 저장하면 안 되는 파일

- AI 추출·규칙·RAG 로직 (→ `ai/`, 중복 구현 금지)
- 실제 개인정보·계약 문서, 업로드 원본
- API 키·비밀정보 (→ `.env`)

## 다른 폴더와의 연결

- `ai/` 패키지를 호출한다. AI 내부 로직을 재구현하지 않는다.
- `frontend/`와 API 스키마를 동기화한다. (`docs/api/`)

## 현재 상태 / TODO

- `main.py` 헬스체크 스텁만 존재. 엔드포인트·서비스·저장소 미구현.
- TODO: FastAPI 의존성 확정 후 `pyproject.toml` 갱신
- TODO: 실행 명령 (예: uvicorn) 확정 후 이 README에 기록
- TODO: DB 확정 → `models/`·`repositories/` 구현
- TODO: 인증 방식 확정 → 도입
