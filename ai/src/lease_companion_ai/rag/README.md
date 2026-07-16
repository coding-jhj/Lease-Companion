# rag/

## 책임

법령·표준 주택임대차계약서·공공기관 가이드 등 **공식 자료 기반 근거를 검색**한다. **판정을 내리지 않는다.** 근거가 없으면 규칙 결과를 유지하고 `evidence_sources=[]`를 반환한다.

## 하위 구조

- `indexing/` — 공식 자료 청크·임베딩 인덱스 구축 (자료·메타데이터는 `data/rag/`)
- `retrieval/` — 판정·조항 문맥으로 관련 근거 검색
- `reranking/` — 검색 결과 재정렬로 근거 정확도 향상
- `citations/` — 근거에 기관명·문서명·URL·발행/확인일 출처 부착

## 입력

- 판정 결과·조항 문맥 (근거가 필요한 항목)

## 출력

- 항목별 공식 근거 스니펫 + 출처 인용
- 근거 없음 시 `evidence_sources=[]` 반환 (임의 생성·규칙 판정 변경 금지)

## 확정 / TODO

- 확정: 임베딩 gemini-embedding-001 + BM25, 리랭커 Cohere rerank-v4.0-pro(2026-07-14 선정표). 벡터 저장소 **Chroma 로컬 모드**(2026-07-16, `../../../../docs/decisions/2026-07-16-mvp-platform-stack.md`).
- 구현 완료(배치 1): `models.py` 내부 계약, `indexing/chunker.py` 결정적 청킹, `retrieval/bm25.py` 로컬 검색, embedding·rerank provider protocol과 fake provider 테스트.
- 구현 완료(배치 2): 공식 출처 manifest, Chroma 로컬 인덱스와 stale 탐지, Gemini embedding 어댑터, RRF hybrid Top-20, Cohere rerank Top-5와 실패 fallback.
- 실제 Gemini·Cohere 호출은 키·비용 승인 전까지 실행하지 않는다. 현재 어댑터 검증은 주입한 fake SDK client만 사용한다.
- TODO: 이용조건이 명시적으로 허용된 공식 원문 수집, 규칙 결과 enrichment.
