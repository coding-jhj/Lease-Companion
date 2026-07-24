# RAG 설계

## 역할

공식 법령·표준계약서·공공기관 가이드에서 근거를 검색해, 판정·질문·체크리스트·행동에 출처를 연결한다.

## 판정 분리 원칙

- RAG(`rag`)는 **근거 검색**만 담당한다. 계약 가능·안전·전세사기·합법 여부를 **판정하지 않는다.** 최종 판정은 규칙 엔진이 한다.
- 검색된 근거는 사용자가 확인할 수 있도록 출처와 함께 제시한다.
- 근거가 없으면 지어내지 않고 `evidence_sources=[]`를 반환한다. RAG 근거 부족을 이유로 규칙 엔진의 `RuleStatus`·`urgency`·`reason`을 변경하지 않는다.

## 파이프라인 내 위치

규칙 엔진 판정 뒤에 위치해, 각 판정과 생성될 질문·행동의 **공식 근거**를 붙인다. 저신뢰 결과의 상용 LLM 재검토와 쉬운 설명·질문·행동 생성은 RAG가 제공한 근거를 사용한다.

## 자료 기준

- 공식 출처 우선. 블로그·커뮤니티 자료를 핵심 근거로 쓰지 않는다.
- 자료마다 기관명·문서명·URL·발행일/확인일 기록. (`../data/rag-sources.md`)
- 인용 정확성(제시한 근거가 실제 출처 내용과 일치)은 평가 대상이다. (`evaluation-matrix.md`)

## 확정 (2026-07-14 선정표)

- 임베딩: gemini-embedding-001 + BM25 하이브리드(Top-20)
- 재랭킹: Cohere rerank-v4.0-pro(Top-5)
- 벡터 저장소: Chroma 로컬 모드
- 로컬 lexical 검색: 결정적 Okapi BM25
- 검색 provider 경계: embedding·rerank protocol로 SDK 호출부를 격리

## 배치 1 구현 상태 (2026-07-16)

- `rag/models.py`: 공식자료 메타데이터·청크·비식별 검색 질의·검색 hit 내부 계약
- `rag/indexing/chunker.py`: source hash·section·ordinal·text 기반 결정적 `chunk_id`
- `rag/retrieval/bm25.py`: 추가 패키지 없는 결정적 BM25와 `chunk_id` 동점 정렬
- `providers/embeddings.py`·`providers/rerank.py`: 외부 SDK와 분리된 protocol·응답 검증
- dev/test retrieval 정답과 `rule_evidence_map.csv`는 `official_verified` source ID만 허용

## 배치 2 구현 상태 (2026-07-16)

- 공식 검증 출처 10개는 `data/rag/metadata/official_sources.jsonl` manifest로 고정했다. 자유이용이 확인된 법령 3개와 법령 서식 `SRC-CONFIRM-FORM`, 공공누리 제1유형인 법무부 표준 주택임대차계약서 1개, 팀 예외 규정(2026-07-20) 적재한 `SRC-MOLIT-CHECKLIST` 1개는 정규화 원문과 SHA-256을 보존하고, 나머지 4개는 `metadata_only`로 둔다.
- `chromadb>=1.5,<2` 로컬 인덱스에 source hash·청킹 버전·embedding model fingerprint를 기록한다. fingerprint 변경은 stale 인덱스로 탐지하고, 호출자가 `rebuild=True`를 명시한 경우에만 기존 컬렉션을 교체한다.
- `GeminiEmbeddingProvider`는 `gemini-embedding-001`, 문서 `RETRIEVAL_DOCUMENT`, 질의 `RETRIEVAL_QUERY`, 768차원을 사용한다.
- BM25와 vector 순위는 RRF(`rrf_k=60`)로 결정적으로 결합한다. 원점수가 서로 다른 척도이므로 점수 정규화보다 순위 결합을 사용한다. 동점은 `chunk_id` 오름차순이다.
- hybrid Top-20을 `rerank-v4.0-pro` Top-5로 재정렬한다. vector 실패 시 BM25, rerank 실패·빈 응답 시 hybrid 순위를 유지한다.
- 실제 Gemini·Cohere 유료 호출은 하지 않았다. SDK 어댑터는 fake client로 검증했다.

## 배치 3 구현 상태 (2026-07-17)

- R01~R10 행동 발동 결과에 로컬 공식 원문 검색 결과만 연결한다. `RuleStatus`·`urgency`·`reason` 등 판정 필드는 검색 전후 동일하게 유지한다.
- dev 34건과 최종 test 10건을 분리해 Top-5 포함률·전체 및 로컬 가용 expected source recall·인용 메타데이터·비공식 출처 노출을 측정했다. 기대 source 누락은 원문 부재, R allowlist 제외, BM25 Top-20 후보 누락, Top-5 밖으로 분류한다. 원문 부재는 중복 제거 source ID 목록으로, 나머지는 검색 개선을 위해 사례 ID·규칙 ID·source ID를 남긴다. 결과는 `data/rag/evaluation/`에 있다.
- 검색 가능한 로컬 원문은 법령 3개, 중개대상물 확인·설명서 1개, 표준 주택임대차계약서 1개, 안심 전세계약 체크리스트 1개다. 나머지 정답 출처는 metadata-only이므로 목표값으로 보정하지 않고 실측값과 제한을 함께 기록한다.
- 배치 3 당시 최종 test 기준 전체 기대 source recall은 4/39(10.26%)이고, 로컬 가용 기대 source recall은 4/5(80%)다. 누락은 원문 부재 34개와 BM25 후보 누락 1개이며, 검색 알고리즘·질의 개선 대상은 후자다.
- 2026-07-21 `SRC-CONFIRM-FORM` 승격 후 최종 test R 기준 전체·로컬 가용 expected source recall은 39/39(100%)이며 비공식 출처 노출은 0이다. J 기준은 33/41(80.49%)이고, 나머지 8개는 로컬 원문이 없는 공식 출처다.

## 배치 4 구현 상태 (2026-07-18)

- `analyze_snapshot()`의 기본 evidence factory를 영속 Chroma vector+BM25 RRF Top-20 경로로 연결했다. Gemini 키가 없거나 embedding·Chroma 준비가 실패하면 BM25로 축소한다.
- Cohere 키가 있으면 공식 검증 후보를 `rerank-v4.0-pro` Top-5로 재정렬한다. rerank 실패·빈 응답은 hybrid/BM25 순서를 유지한다.
- source hash·청킹 버전·embedding model fingerprint가 같은 인덱스는 재임베딩하지 않는다. stale fingerprint는 생성 인덱스 컬렉션만 자동 재구축한다.
- runtime factory·동일 인덱스 재사용·stale 재구축·BM25 fallback은 fake provider와 임시 Chroma client로 검증했다. 실제 유료 호출은 수행하지 않았다.

## 배치 5 구현 상태 (2026-07-18)

- R01~R10의 `RetrievalQuery`와 분리된 J01~J13 전용 `JudgmentRetrievalQuery`를 추가했다. J 질의는 판정 ID·판정명·상태·선택적 비식별 문맥과 판정별 허용 source ID를 포함한다.
- 판정별 허용 source ID는 `data/rules/judgment_spec.csv`의 `official_source_ids`를 단일 입력으로 읽는다. 검색 후보는 이 allowlist에 포함된 `official_verified` 청크만 남긴 뒤 Top-5를 구성한다.
- 행동이 발동된 J 판정만 근거를 보강한다. 검색 전후 `status`·`urgency`·`reason`은 동일하며, 허용 원문이 로컬 corpus에 없으면 다른 유사 자료를 붙이지 않고 `evidence_sources=[]`를 유지한다.
- 표준 주택임대차계약서와 안심 전세계약 체크리스트는 로컬 원문으로 검색할 수 있다. 등기 자료 등 metadata-only 출처만 허용된 J 항목은 기본 로컬 실행에서 `evidence_sources=[]`가 될 수 있으며, 검색 성공률을 임의로 보정하지 않는다.

## 배치 6 구현 상태 (2026-07-19)

- `SRC-STD-LEASE`를 공공누리 제1유형 이용조건에 따라 `local_source`로 승격하고, 서식 입력란을 제외한 법적 본문을 정규화해 적재했다.
- manifest·source inventory·retrieval 평가를 새 원문 구성에 맞춰 결정적으로 갱신했다. 판정 필드 불변과 비공식 출처 노출 0 기준은 유지한다.

## 특약 전용 검색 구현 상태 (2026-07-22)

- `ClauseRetrievalQuery`는 catalog ID·표시명, 연결 R/J 이름·상태, 비식별 특약 원문, 허용 source·section을 하나의 검색 계약으로 고정한다.
- `special_clause_evidence_map.csv`에 적힌 조·항만 공식 원문에서 결정적으로 추출한다. 법 조문, 항 범위, 대괄호 섹션, 체크리스트 항목을 보존한다.
- BM25는 특약 질의에서 허용 source·section 후보만 검색한다. API 키 없이 한국어 n-gram BM25를 사용하고, embedding·rerank provider를 주입하면 기존 Chroma hybrid Top-20·rerank Top-5 경로를 재사용한다.
- 최종 특약 근거는 동일 source·section 청크를 제거한 Top-3다. 검색 실패·근거 없음은 빈 `evidence_sources`이며 R/J 상태·시급도·사유는 바꾸지 않는다.
- 실제 Gemini embedding·Cohere 호출은 하지 않았다. 잠긴 retrieval 7건은 Fake reranker로 source·section 순위를 검증했다.
- 작업 5는 독립 enrichment 서비스를 완성한 범위다. 분석 파이프라인 자동 호출은 작업 7에서 generation·guardrail과 함께 연결한다.

## 후속 TODO

- 재배포 조건이 명시적으로 허용된 공식 원문의 실제 문서 구조를 확인한 뒤 기본 청킹 크기(`1200`)·중첩(`120`)을 평가
- metadata-only 공식자료 4개는 적합한 근거 범위와 이용조건을 추가 확인한 뒤 허용 원문만 적재
- metadata-only 원문 추가 후 J01~J13 판정별 retrieval goldset·source recall 측정
- 별도 키·비용 승인 후 Gemini·Cohere smoke test와 실측 latency·비용 기록
- 작업 7에서 `SpecialClauseRetrievalService.enrich()`를 catalog→R/J 뒤, 생성 앞에 연결
