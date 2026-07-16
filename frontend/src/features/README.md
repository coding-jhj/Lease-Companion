# src/features/

흐름 단계별 기능 모듈 디렉터리. 각 디렉터리는 이미 존재하며 `.gitkeep`으로 유지한다. **`.gitkeep`을 삭제하지 않는다.** 스택은 React + Vite + TypeScript로 확정(2026-07-16) — 코드 채움은 프로젝트 초기화 후 구현 작업에서 진행한다.

## 최신 feature 책임 (한 줄)

| feature | 단계 | 책임 |
|---------|------|------|
| `auth` | 1 | 회원가입·로그인·세션 |
| `contracts` | 2 | 계약 건 목록·생성·조회 관리 |
| `contract-stage` | 3 | 계약 상황(단계·유형) 입력 |
| `document-upload` | 4 | 계약서·등기 등 문서 업로드 |
| `extraction-review` | 5 | AI 추출값 확인·수정 |
| `judgment-results` | 7 | 12개 판정 결과 표시 (결과 상태 9개·시급도 5개) |
| `evidence-sources` | 7 | 원문 증거·공식 근거(RAG) 표시 |
| `question-cards` | 7 | 임대인·공인중개사 대상 확인 질문 카드 |
| `signing-checklist` | 8 | 서명 전 체크리스트 |
| `post-contract-actions` | 8 | 계약 직후 권리 확보 행동 관리 |
| `result-feedback` | 7·8 | 결과에 대한 사용자 피드백 |

## 기존 디렉터리와의 관계 (삭제하지 말 것)

- `verification-items` — 구 "확인 필요 항목" 모듈. 최신 구조에서는 `judgment-results`(판정·상태)와 `question-cards`(확인 질문)로 세분화됨. 정리·이관 결정 전까지 유지한다.
- `result-report` — 구 결과 요약 모듈. 최신 구조에서 리포트는 페이지(`src/pages/result-report`)가 담당하고, 내용은 `judgment-results`·`evidence-sources`·`question-cards`·`post-contract-actions` feature를 조합해 구성한다. 정리 결정 전까지 유지한다.

두 디렉터리의 통합·제거는 별도 결정(`docs/decisions/`) 후 진행한다. 이번 정비에서는 삭제하지 않는다.
