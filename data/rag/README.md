# data/rag/

**공식 근거 자료**(RAG) 보관 위치. 출처·메타데이터 기준: [`../../docs/data/rag-sources.md`](../../docs/data/rag-sources.md).

> RAG는 근거 검색·설명만 담당한다. **판정을 내리지 않는다**(판정은 규칙 엔진, [`../../docs/data/judgment-spec.md`](../../docs/data/judgment-spec.md)).

## 하위 구조

| 폴더 | 내용 |
|------|------|
| `sources/` | 공식 원문 자료 (법령·표준계약서·공공기관 가이드) |
| `chunks/` | 검색용 청크 (원본에서 분할) |
| `metadata/` | 자료별 필수 메타데이터 |
| `evaluation/` | 검색(retrieval) 품질 평가 데이터 |

## 필수 메타데이터 (`metadata/`)

자료마다 다음을 기록한다.

| 필드 | 의미 |
|------|------|
| `document_title` | 자료명 |
| `institution` | 발행기관 |
| `article_or_section` | 조문·항목 |
| `effective_date` | 시행일 (법령·표준서식) |
| `source_url` | 원문 URL |
| `collected_date` | 수집일 |
| `document_type` | 문서 유형 (법령 / 표준계약서 / 공공기관 가이드 등) |
| `source_sha256` | 수집 원문 또는 정규화 원문의 SHA-256 |
| `usage_terms` | 저장·재배포·인용 가능 범위 |

## 원칙

- 공식 법령·표준 주택임대차계약서·공공기관 자료를 우선한다. 블로그·카페·커뮤니티는 핵심 근거로 쓰지 않는다.
- `source_inventory.csv`의 `source_status=official_verified`와 공식 원문 URL·발행기관이 모두 확인된 자료만 `OfficialSource`로 노출한다.
- `synthetic_reference`·`unverified`·`excluded`는 구조·평가 참고에만 쓰며 `evidence_sources`에서 제외한다.
- 검색 근거가 0개여도 규칙 엔진의 `RuleStatus`·`urgency`는 바꾸지 않고 `evidence_sources=[]`로 둔다.
- `sources`·`chunks`·`metadata`·`evaluation`을 분리한다.
- 벡터 저장소는 Chroma 로컬 모드로 확정했다. 생성 인덱스(`data/rag/index/`, Chroma 영속 디렉터리)는 Git에서 제외한다.
- 공식 원문은 이용조건을 확인한 뒤에만 수집·재배포한다. 허용되지 않으면 URL·해시·수집 절차만 관리한다.

## 현재 상태 / TODO

- 공식자료 후보 16개의 검증 상태는 `../rules/source_inventory.csv`, 공식 검증 10개의 결정적 manifest는 `metadata/official_sources.jsonl`에 기록했다.
- 법령 3개(`SRC-HTA-LAW`·`SRC-HTA-DECREE`·`SRC-CIVIL-LEASE`), 법령 서식 `SRC-CONFIRM-FORM`, 법무부 표준 주택임대차계약서는 자유이용·공공누리 제1유형 근거를 확인해 정규화 원문과 SHA-256을 보존한다. `SRC-MOLIT-CHECKLIST`는 2026-07-20 팀 예외 규정으로 로컬 원문을 적재한다. 나머지 4개는 `metadata_only`로 원문을 커밋하지 않는다.
- 배치 1 완료: 공식 source ID 전용 map·dev/test goldset 계약, RAG 내부 모델, 결정적 청킹, 로컬 BM25, provider protocol과 fake provider 검증.
- 배치 2 완료: Chroma 로컬 인덱스·stale 탐지, Gemini embedding, RRF hybrid, Cohere rerank 어댑터와 offline 검증. 생성 인덱스는 Git에서 제외한다.
- 배치 3 완료: R01~R10 공식 근거 enrichment와 분리된 dev/test retrieval 평가.
- 배치 6 완료: `SRC-STD-LEASE` 로컬 원문 승격과 R/J retrieval 평가 갱신.
- 배치 8 완료(2026-07-20): `SRC-MOLIT-CHECKLIST` 팀 예외 규정 로컬 원문 적재. test R recall 15/39→38/39, J recall 30/41→33/41, 로컬 가용 recall 1.0·비공식 노출 0 유지.
- 배치 9 완료(2026-07-21): 국가법령정보센터 자유이용 정책을 확인한 `SRC-CONFIRM-FORM` 정규화 원문 적재. test R recall 38/39→39/39, J recall 33/41 유지, 로컬 가용 recall 1.0·비공식 노출 0 유지.
- TODO: 재배포가 명시적으로 허용된 공식 원문 추가. Gemini·Cohere 실호출은 별도 키·비용 승인이 필요하다.
