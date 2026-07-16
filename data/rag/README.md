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

## 원칙

- 공식 법령·표준 주택임대차계약서·공공기관 자료를 우선한다. 블로그·카페·커뮤니티는 핵심 근거로 쓰지 않는다.
- `source_inventory.csv`의 `source_status=official_verified`와 공식 원문 URL·발행기관이 모두 확인된 자료만 `OfficialSource`로 노출한다.
- `synthetic_reference`·`unverified`·`excluded`는 구조·평가 참고에만 쓰며 `evidence_sources`에서 제외한다.
- 검색 근거가 0개여도 규칙 엔진의 `RuleStatus`·`urgency`는 바꾸지 않고 `evidence_sources=[]`로 둔다.
- `sources`·`chunks`·`metadata`·`evaluation`을 분리한다.
- 벡터 저장소는 Chroma 로컬 모드로 확정했다. 생성 인덱스(`data/rag/index/`, Chroma 영속 디렉터리)는 Git에서 제외한다.
- 공식 원문은 이용조건을 확인한 뒤에만 수집·재배포한다. 허용되지 않으면 URL·해시·수집 절차만 관리한다.

## 현재 상태 / TODO

- 원문·청크·Chroma 인덱스는 아직 없다. 공식자료 후보 15개의 검증 상태와 메타데이터는 `../rules/source_inventory.csv`에 기록했다.
- TODO: 검증된 자료의 이용조건 확인 후 원문 수집·결정적 청킹·Chroma 적재·BM25 결합·Cohere rerank 구현.
