# rag/

## 책임

법령·표준 주택임대차계약서·공공기관 가이드 등 **공식 자료 기반 근거를 검색**한다. **판정을 내리지 않는다.** 근거가 없으면 규칙 결과를 유지하고 `evidence_sources=[]`를 반환한다.

## 하위 구조

- `indexing/` — 공식 자료 청크·임베딩 인덱스 구축 (자료·메타데이터는 `data/rag/`)
- `retrieval/` — 판정·조항 문맥으로 관련 근거 검색
- `reranking/` — 검색 결과 재정렬로 근거 정확도 향상
- `models.py` — 청크·출처 메타데이터·R/J 검색 입출력 계약
- `service.py` — allowlist 적용, R/J 근거 조립과 기관명·문서명·URL 인용 생성

## 입력

- 판정 결과·조항 문맥 (근거가 필요한 항목)

## 출력

- 항목별 공식 근거 스니펫 + 출처 인용
- 근거 없음 시 `evidence_sources=[]` 반환 (임의 생성·규칙 판정 변경 금지)

## 확정 / TODO

- 확정: 임베딩 gemini-embedding-001 + BM25, 리랭커 Cohere rerank-v4.0-pro(2026-07-14 선정표). 벡터 저장소 **Chroma 로컬 모드**(2026-07-16, `../../../../docs/decisions/2026-07-16-mvp-platform-stack.md`).
- 구현 완료(배치 1): `models.py` 내부 계약, `indexing/chunker.py` 결정적 청킹, `retrieval/bm25.py` 로컬 검색, embedding·rerank provider protocol과 fake provider 테스트.
- 구현 완료(배치 2): 공식 출처 manifest, Chroma 로컬 인덱스와 stale 탐지, Gemini embedding 어댑터, RRF hybrid Top-20, Cohere rerank Top-5와 실패 fallback.
- 구현 완료(배치 3): R01~R10 행동 발동 결과 뒤에서 실제 로컬 검색 근거만 연결하며 규칙 판정 필드를 보존. 분리된 dev/test retrieval 평가와 실측 결과를 `data/rag/evaluation/`에 기록.
- 구현 완료(배치 4): 기본 runtime factory가 Gemini 키 존재 시 영속 Chroma+BM25 RRF Top-20을 구성하고, Cohere 키 존재 시 Top-5 rerank를 연결한다. 동일 fingerprint는 재임베딩하지 않고 stale index는 자동 재구축한다. 키·embedding·vector·rerank·인덱스 실패는 BM25 또는 hybrid 순서로 fallback한다.
- 구현 완료(배치 5): J01~J12는 별도 `JudgmentRetrievalQuery`를 사용하고 `judgment_spec.csv`의 판정별 source allowlist에 포함된 공식 청크만 근거로 연결한다. allowlist 원문이 없으면 J 판정과 시급도를 유지한 채 `evidence_sources=[]`로 남긴다.
- 구현 완료(배치 6): 법무부 표준 주택임대차계약서 `SRC-STD-LEASE`를 공공누리 제1유형 조건에 따라 로컬 원문으로 승격하고 R/J retrieval 평가를 갱신했다. 현재 로컬 원문은 법령 2개와 표준계약서 1개다.
- 실제 Gemini·Cohere 호출은 키·비용 승인 전까지 실행하지 않는다. 현재 어댑터 검증은 주입한 fake SDK client만 사용한다.
- TODO: metadata-only 공식자료 6개 중 재배포가 허용되는 원문을 추가하고 R/J retrieval을 재평가. 별도 키·비용 승인 후 Gemini·Cohere smoke test.
