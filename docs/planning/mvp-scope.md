# MVP 범위

> MVP는 **PoC에서 검증한 기술을 통합한 실제 사용자 서비스**다. PoC(`poc-scope.md`)와 서로 다른 기능 목록이 아니라, 검증 단계(PoC)와 서비스 단계(MVP)의 관계다.

## 최신 MVP 정의

회원 기반 모바일 웹앱에서 사용자가 계약 건과 계약 문서를 관리하고, 상용 LLM(Gemini 3.5 Flash)이 임대차 조항 유형과 불명확성 후보를 구조화한다. Python 규칙 엔진은 계약서와 관련 문서의 값을 교차검증하고, 공식자료 RAG와 상용 LLM(Gemini 3.5 Flash)은 판정 근거·쉬운 설명·확인 질문·사용자 행동을 생성한다. 파인튜닝한 로컬 7B 모델은 상용 vs 로컬 성능비교 병렬 실험(선택)으로만 유지하며 MVP 크리티컬 패스에서 제외한다.

## 사용자 기능 흐름 (8단계)

1. 회원가입·로그인
2. 계약 대시보드·계약 건 생성
3. 계약 상황 입력
4. 계약서·등기 등 문서 업로드
5. 추출값 확인·수정
6. 상용 LLM 구조화·규칙 엔진·RAG·상용 LLM 분석
7. 판정·원문 증거·공식 근거·질문·행동 리포트
8. 저장된 체크리스트·계약 직후 행동 관리

상세: [user-flow.md](user-flow.md)

## 병렬 확장 모드: 계약 연습 시뮬레이션

> 상태: 2026-07-22 승인된 합성 시나리오 3개가 AI 답변 평가, Backend 세션·턴·결과 저장 API, Frontend 텍스트 대화·복기 화면과 연결됐다. 실제 Gemini 네트워크 품질과 아바타 미디어는 미검증·후속 범위다. 기존 실전 계약 점검 8단계를 대체하지 않는다.

- 승인된 합성 계약 상황에서 가상 임대인·공인중개사와 확인 대화를 연습한다.
- 계약 규칙·공식자료 RAG·Guardrail은 재사용하되, 실제 계약 `contract_id`와 연습 세션·행동 평가는 분리한다.
- 현재 텍스트 세로 흐름은 조건부 보증금 반환, 제3자 계좌 송금, 대리인 권한 미확인 3개 시나리오다. 행동 기반 복기와 공식 근거를 제공한다.
- 사전 제작 영상·캐릭터 이미지·image-to-video·음성합성은 현재 구현 범위 밖이며 제공자는 TODO다.
- 상세: [`practice-simulation-product-rules.md`](practice-simulation-product-rules.md), [`../decisions/2026-07-20-practice-simulation-boundary.md`](../decisions/2026-07-20-practice-simulation-boundary.md)

## 포함 범위

- 회원가입·로그인·로그아웃·회원 탈퇴
- 사용자별 계약 건 생성·조회·삭제
- 계약 단계·계약 상황 입력
- 계약서·특약 필수 업로드 / 등기사항증명서·중개대상물 확인설명서 선택 업로드
- 디지털 PDF 텍스트 추출(PyMuPDF·PDF.js), 스캔 PDF·사진 OCR(상용 LLM Gemini 3.5 Flash VLM 통합)
- 핵심 정보 구조화 + 사용자 추출값 확인·수정
- 상용 LLM(Gemini 3.5 Flash) 조항 유형·명확성 후보 구조화 (선택: 로컬 7B 성능비교 실험 — MVP 크리티컬 패스 제외)
- Python 규칙 엔진 문서 내부 판정과 문서 교차검증 (12개 판정)
- 등기사항증명서 교차검증
- 사용자 확인 특약의 결정론적 11유형 후보 매칭과 Python J09~J13 최종 판정
- 특약 원문·R/J 상태·허용 source/section 기반 공식 법령·공공자료 Top-3 RAG
- 상용 LLM 쉬운 설명·확인 질문·수정 요청·행동 생성 및 저신뢰 결과 재검토
- 판정·원문 증거·공식 근거·질문·행동·특약 확인 카드·전체 리포트 PDF
- 결과 저장·재조회
- 서명 전 체크리스트 상태 저장
- 계약 직후 행동 상태 저장
- 추출·판정·근거 오류 사용자 피드백

## 판정 (4영역 13항목)

J01–J13. 상세와 상태·시급도 매핑: [../data/judgment-spec.md](../data/judgment-spec.md)

## 구현 순서 (2026-07-16 확정)

전체 MVP 목표는 그대로 J01~J13이며, 구현은 두 단계로 진행한다.

1. **1단계**: R01~R10 기반 실전 계약 점검 MVP 완성 (업로드 → 계약 상황 입력 → 추출·확인·수정 → R01~R10 → 근거·질문·행동 → 저장·재조회)
2. **2단계**: J01~J13 전체 판정 확장 (R↔J 매핑은 [../data/judgment-spec.md](../data/judgment-spec.md) 관리, 기존 필드 하위 호환 유지)
3. **확장 단계**: R11~R24 추가. R11~R15·R17~R18은 확인 입력 기반, R16·R23·R24는 질문·체크리스트 기반이다. R19는 시점별 등기 이력, R20~R22는 외부 데이터가 연결되기 전까지 `확인 불가`로 제공한다.

단계별 선행 조건·완료 기준: [mvp-execution-plan.md](mvp-execution-plan.md)

## 제외 범위

- 부동산 매매, 상가·사무실 임대차, 경매·공매, 소송
- 계약 종료·보증금 반환 분쟁, 거주 중 하자 대응
- 계약 안전·전세사기 여부 단정, 적법·위법 확정, 계약 체결 추천·거절
- 도장·서명·신분증 진위 판정, 법률 상담 대체
- (후순위) 결제, 알림 등 부가 기능

## 비고

- 플랫폼 확정(2026-07-16, → [`../decisions/2026-07-16-mvp-platform-stack.md`](../decisions/2026-07-16-mvp-platform-stack.md)): DB **PostgreSQL**, 인증 **JWT Bearer(Python: PyJWT + Passlib-bcrypt)**, 프론트엔드 **React + Vite + TypeScript**, Vector DB **Chroma 로컬 모드**. refresh token·운영 키 정책과 운영 배포 플랫폼은 TODO다.
- 통합 스키마는 `ai/src/lease_companion_ai/schemas/` Pydantic 단일 원본(→ [`../decisions/2026-07-16-shared-pydantic-schema.md`](../decisions/2026-07-16-shared-pydantic-schema.md)).
- 특약 RAG는 API 키 없는 오프라인 구현·자동 검증까지 완료했다. 잠긴 평가셋 독립 검토와 실제 Gemini·Cohere 검증 전에는 `human_reviewed`·운영 검증 완료로 표시하지 않는다.
- OCR은 상용 LLM Gemini 3.5 Flash VLM 통합(디지털 PDF는 PyMuPDF·PDF.js), 조항 구조화·필드 추출과 설명·질문·행동 생성은 Gemini 3.5 Flash, 임베딩·검색은 gemini-embedding-001+BM25, 리랭커는 Cohere rerank-v4.0-pro로 확정. VLM은 Gemini에 통합되어 별도 OCR·VLM 단계 없음(2026-07-14 변경, → [`../decisions/2026-07-14-ocr-gemini-integration.md`](../decisions/2026-07-14-ocr-gemini-integration.md)). PaddleOCR-VL은 (선택) 비교실험. 벡터 DB는 Chroma 로컬 모드로 확정(2026-07-16).
- 파인튜닝 로컬 7B 베이스 모델은 상용 vs 로컬 성능비교 병렬 실험(선택)으로만 유지하며 MVP 크리티컬 패스에서 제외한다.
