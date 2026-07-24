# src/features/

흐름 단계별 기능 모듈 디렉터리. React + Vite + TypeScript 초기화와 핵심 feature 구현이 완료됐으며, 실제 추적 파일이 있는 디렉터리에는 `.gitkeep`을 두지 않는다.

## 현재 추적 중인 feature 책임

| feature | 단계 | 책임 |
|---------|------|------|
| `document-upload` | 4 | 필수 계약서·선택 문서별 업로드 카드와 개별 상태·재시도 |
| `extraction-review` | 5 | 문서별 AI 추출 필드 카드 확인·수정 |
| `analysis-progress` | 6 | 실제 분석·안내 생성 상태를 4단계 타임라인으로 표시 |
| `judgment-results` | 7 | J01~J13을 사용자용 화면 우선순위 3단계로 표시. R01~R24는 질문·행동 생성과 legacy R-only 결과의 fallback에 사용 |
| `damage-patterns` | 7 | 기존 R/J 판정을 피해 유형 관점으로 묶은 참고 정보 표시 |
| `evidence-sources` | 7 | 원문 증거·공식 근거(RAG) 표시 |
| `special-clauses` | 7 | 확인 특약 원문·판정·공식 근거·질문·수정 요청 표시 |
| `question-cards` | 7 | 중복을 제거한 질문·체크리스트·직후 행동 방어 허브 |
| `result-report` | 7·8 | 판정·근거·질문·행동 모듈을 조합하는 결과 리포트 |
| `result-feedback` | 7·8 | 결과에 대한 사용자 피드백 |

회원·계약 관리와 계약 연습 화면은 현재 `src/pages/`·`src/components/`·`src/services/`에서 조합한다. 존재하지 않는 feature 디렉터리를 구현 완료로 기록하지 않는다.
