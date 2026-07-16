# 2026-07-16 — MVP 플랫폼 스택 확정

- **상태**: 확정 (2026-07-16 팀 합의)
- **범위**: 실전 계약 점검 MVP의 플랫폼 기술 선택. 운영 배포 플랫폼은 이 결정에 포함하지 않는다(미정 유지).

## 결정

| 항목 | 결정 | 비고 |
|------|------|------|
| 데이터베이스 | **PostgreSQL** | 회원·계약 건·문서·분석 결과 영속 저장 |
| 인증 | **JWT Bearer + bcrypt 계열 비밀번호 해시** | 방식 확정. 구체 라이브러리는 TODO |
| 프론트엔드 | **React + Vite + TypeScript** | `frontend/` 초기화 가능 (이 문서 작성 시점 미초기화) |
| Vector DB | **Chroma (로컬 모드)** | 공식자료 RAG 인덱스 저장소 |
| 실행 방식 | **현재 MVP는 로컬 실행** | 운영 배포 플랫폼 확정이 아니다 |
| 운영 배포 플랫폼 | **미정 (TODO)** | 별도 결정 필요 |

## 선택 이유

- **PostgreSQL**: 영속 저장 필요성은 이미 확정된 상태였고, 실서비스 수준 DB를 처음부터 사용해 후속 마이그레이션 비용을 없앤다.
- **JWT Bearer + bcrypt 계열**: 회원 기능은 MVP 확정 범위. 무상태 토큰 방식이 FastAPI 구조(의존성 주입 기반 인증 주체 확인)와 맞고, bcrypt 계열은 검증된 비밀번호 해시 표준이다.
- **React + Vite + TypeScript**: 모바일 웹앱 요구와 Backend/OpenAPI 타입 동기화 요구(TypeScript)를 충족하는 범용 조합.
- **Chroma 로컬 모드**: 설치·운영 부담이 가장 낮아 로컬 실행 MVP에 적합. 확정된 임베딩·검색 구성(gemini-embedding-001 + BM25, Cohere rerank-v4.0-pro)과 독립적으로 인덱스 저장소만 담당한다.
- **로컬 실행**: 발표·검증까지 배포 인프라 없이 팀 전원이 동일 환경을 재현할 수 있다.

## 현재 제약

- 로컬 실행이므로 팀 외부 접근·상시 가동은 불가하다.
- Chroma 로컬 모드는 단일 프로세스 기준이며 대규모 동시 검색을 전제하지 않는다.
- 대용량 벡터 인덱스·DB 데이터는 Git에 커밋하지 않는다(기존 원칙 유지).

## 미정으로 남는 항목 (TODO — 임의 확정 금지)

- JWT 구현 라이브러리, 토큰 만료 시간, refresh token 여부, 토큰 폐기 방식, 서명 키 관리 방식
- bcrypt 계열 구체 라이브러리
- 운영 배포 플랫폼 (frontend·backend·DB·Vector DB 호스팅)
- 상용 LLM 리전, CI/CD, 환경 분리(dev/stage/prod), 시크릿 관리 방식

## 재검토 조건

- 운영 배포 플랫폼 결정 시: 로컬 실행 전제(Chroma 로컬 모드 포함) 재검토.
- RAG corpus·트래픽이 Chroma 로컬 모드의 한계를 넘을 때: Vector DB 재선정.
- 인증 요구(소셜 로그인·세션 무효화 등) 확장 시: JWT 정책 상세 확정과 함께 재검토.

## 대체·갱신하는 기존 TODO 문서

이 결정으로 다음 문서의 "미정" 표기가 갱신된다.

- 루트 `AGENTS.md` — 미정 기술 표 (프론트엔드·DB·벡터 DB·인증·배포)
- `frontend/AGENTS.md`, `frontend/README.md` — 스택 미정·코드 생성 금지
- `backend/AGENTS.md`, `backend/README.md` — DB·인증 미확정, models/repositories 구현 보류
- `ai/AGENTS.md`, `ai/README.md`, `ai/src/lease_companion_ai/rag/README.md` — 벡터 DB 제품 미정
- `docs/planning/mvp-scope.md`, `docs/planning/minimum-mvp-v1.md`
- `docs/architecture/system-architecture.md` · `deployment.md` · `data-flow.md` · `ai-pipeline.md`
- `docs/backend/auth-and-persistence.md`, `docs/api/api-overview.md`
