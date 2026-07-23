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

- LLM 제공자·모델: 구조화·OCR·생성 Gemini 3.5 Flash. 생성 provider 통합 → [`2026-07-20-gemini-generation-provider.md`](2026-07-20-gemini-generation-provider.md)
- 임베딩·검색: gemini-embedding-001 + BM25 → Cohere rerank-v4.0-pro (2026-07-14 선정표)
- OCR: Gemini VLM 통합 → [`2026-07-14-ocr-gemini-integration.md`](2026-07-14-ocr-gemini-integration.md)
- 플랫폼 스택: PostgreSQL / JWT Bearer + bcrypt 계열 / React + Vite + TypeScript / Chroma 로컬 모드 / 현재 로컬 실행 → [`2026-07-16-mvp-platform-stack.md`](2026-07-16-mvp-platform-stack.md)
- 프론트엔드 구현 스택: React + Vite + TypeScript SPA / React Router / fetch 서비스 계층 / MSW / Vitest + Testing Library / npm → [`2026-07-16-frontend-react-vite.md`](2026-07-16-frontend-react-vite.md)
- 통합 스키마: `ai/src/lease_companion_ai/schemas/` Pydantic 단일 원본 → [`2026-07-16-shared-pydantic-schema.md`](2026-07-16-shared-pydantic-schema.md)
- Classification 경계: extraction은 사실·조항 원문, 별도 classification은 조항 유형·명확성 후보 → [`2026-07-18-classification-boundary.md`](2026-07-18-classification-boundary.md)
- 계약 연습 시뮬레이션: 실전 계약과 데이터 분리 / 승인된 합성 시나리오 / 행동 평가와 계약 판정 분리 / Gemini 기준 이미지·사전 제작 영상 → [`2026-07-20-practice-simulation-boundary.md`](2026-07-20-practice-simulation-boundary.md)
- 특약 R/J 책임 경계: 기존 R08·R09 의미 유지 / R10 문구 확인과 R19 실제 권리변동 분리 / J10·J11·J12 Python 최종 판정 / 신규 R25 미추가 → [`2026-07-22-special-clause-rule-judgment-boundary.md`](2026-07-22-special-clause-rule-judgment-boundary.md)
- 특약 공식근거 RAG: 결정론적 후보→Python R/J→허용 source/section Top-3→grounded 생성 / 근거 없음 질문 전용 / 실제 provider·운영 활성화 보류 → [`2026-07-22-special-clause-evidence-rag.md`](2026-07-22-special-clause-evidence-rag.md)
- J13 임차권 보호 제한 특약: 5개 유형을 J13 하나로 통합 / C영역 확장 / 상태 3개(확인 필요·적용 제외·확인 불가) / J12와 독립 / 카탈로그 단일 출처 / judgment 시퀀스 하위호환 필수 → [`2026-07-23-j13-tenant-protection-restriction.md`](2026-07-23-j13-tenant-protection-restriction.md)

## 현재 미정 (결정 대기)

- 운영 배포 플랫폼 (현재 MVP는 로컬 실행)
- refresh token·토큰 폐기·운영 서명 키 관리와 운영용 토큰 만료 정책
- 로컬 7B 베이스 모델(선택 성능비교 실험용)
- 계약 연습 image-to-video·음성합성 제공자와 운영 미디어 저장소

> 결정 시 이 폴더에 기록하고 관련 README·문서를 갱신한다.
