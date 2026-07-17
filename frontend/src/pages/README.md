# src/pages/

화면(페이지) 단위 디렉터리. React + Vite + TypeScript 초기화와 기본 페이지 구현이 완료됐으며, 실제 추적 파일이 있는 디렉터리에는 `.gitkeep`을 두지 않는다.

사용자 흐름 8단계(루트 `AGENTS.md`)에 대응한다.

| 페이지 | 단계 | 책임 (한 줄) |
|--------|------|-------------|
| `auth` | 1 | 회원가입·로그인 화면 |
| `dashboard` | 2 | 계약 대시보드 — 계약 건 목록, 계약 건 생성 진입 |
| `contract-create` | 2·3 | 계약 건 생성과 계약 상황 입력 |
| `document-upload` | 4 | 계약서·등기 등 문서 업로드 |
| `extraction-review` | 5 | AI 추출값 확인·수정 (분석 전) |
| `analysis-progress` | 6 | 분석 진행 상태 표시 (분석 중/완료 구분) |
| `result-report` | 7 | 판정·원문 증거·공식 근거·질문·행동 리포트 |
| `contract-detail` | 8 | 계약 건 상세 — 저장된 체크리스트·계약 직후 행동 관리 |
