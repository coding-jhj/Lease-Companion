# 결정 기록 (Decisions)

기술·기획 결정을 기록한다. 결정마다 한 파일 또는 항목으로 남긴다.

## 기록 항목 (권장)

- 결정 제목
- 날짜
- 배경 / 문제
- 선택지
- 결정 내용
- 근거
- 영향받는 폴더·문서

## 확정된 결정

- LLM 제공자·모델: 구조화·OCR Gemini 3.5 Flash / 생성 GPT-5.6 Sol (2026-07-14 선정표)
- 임베딩·검색: gemini-embedding-001 + BM25 → Cohere rerank-v4.0-pro (2026-07-14 선정표)
- OCR: Gemini VLM 통합 → [`2026-07-14-ocr-gemini-integration.md`](2026-07-14-ocr-gemini-integration.md)
- 플랫폼 스택: PostgreSQL / JWT Bearer + bcrypt 계열 / React + Vite + TypeScript / Chroma 로컬 모드 / 현재 로컬 실행 → [`2026-07-16-mvp-platform-stack.md`](2026-07-16-mvp-platform-stack.md)
- 프론트엔드 구현 스택: React + Vite + TypeScript SPA / React Router / fetch 서비스 계층 / MSW / Vitest + Testing Library / npm → [`2026-07-16-frontend-react-vite.md`](2026-07-16-frontend-react-vite.md)
- 통합 스키마: `ai/src/lease_companion_ai/schemas/` Pydantic 단일 원본 → [`2026-07-16-shared-pydantic-schema.md`](2026-07-16-shared-pydantic-schema.md)

## 현재 미정 (결정 대기)

- 운영 배포 플랫폼 (현재 MVP는 로컬 실행)
- refresh token·토큰 폐기·운영 서명 키 관리와 운영용 토큰 만료 정책
- 로컬 7B 베이스 모델(선택 성능비교 실험용)

> 결정 시 이 폴더에 기록하고 관련 README·문서를 갱신한다.
