# src/features/

흐름 단계별 기능 모듈 디렉터리. React + Vite + TypeScript 초기화와 핵심 feature 구현이 완료됐으며, 실제 추적 파일이 있는 디렉터리에는 `.gitkeep`을 두지 않는다.

## 최신 feature 책임 (한 줄)

| feature | 단계 | 책임 |
|---------|------|------|
| `auth` | 1 | 회원가입·로그인·세션 |
| `contracts` | 2 | 계약 건 목록·생성·조회 관리 |
| `contract-stage` | 3 | 계약 상황(단계·유형) 입력 |
| `document-upload` | 4 | 필수 계약서·선택 문서별 업로드 카드와 개별 상태·재시도 |
| `extraction-review` | 5 | 문서별 AI 추출 필드 카드 확인·수정 |
| `analysis-progress` | 6 | 실제 분석·안내 생성 상태를 4단계 타임라인으로 표시 |
| `judgment-results` | 7 | J01~J12를 사용자용 화면 우선순위 3단계로 표시. R01~R24는 질문·행동 생성과 legacy R-only 결과의 fallback에 사용 |
| `evidence-sources` | 7 | 원문 증거·공식 근거(RAG) 표시 |
| `question-cards` | 7 | 중복을 제거한 질문·체크리스트·직후 행동 방어 허브 |
| `signing-checklist` | 8 | 서명 전 체크리스트 |
| `post-contract-actions` | 8 | 계약 직후 권리 확보 행동 관리 |
| `result-feedback` | 7·8 | 결과에 대한 사용자 피드백 |
| `practice-simulation` | 별도 연습 흐름 | 합성 계약서 요약과 대화 중 재확인 UI |

## 기존 디렉터리와의 관계 (삭제하지 말 것)

- `verification-items` — 구 "확인 필요 항목" 모듈. 최신 구조에서는 `judgment-results`(판정·상태)와 `question-cards`(확인 질문)로 세분화됨. 정리·이관 결정 전까지 유지한다.
- `result-report` — 구 결과 요약 모듈. 최신 구조에서 리포트는 페이지(`src/pages/result-report`)가 담당하고, 내용은 `judgment-results`·`evidence-sources`·`question-cards`·`post-contract-actions` feature를 조합해 구성한다. 정리 결정 전까지 유지한다.

두 디렉터리의 통합·제거는 별도 결정(`docs/decisions/`) 후 진행한다. 이번 정비에서는 삭제하지 않는다.
