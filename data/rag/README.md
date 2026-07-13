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
- `sources`·`chunks`·`metadata`·`evaluation`을 분리한다.
- 생성 벡터 인덱스(`data/rag/index/`, `*.faiss` 등)는 Git 제외.

## 현재 상태 / TODO

- `.gitkeep`만 존재. 자료 없음.
- TODO: 실제 출처 수집·메타데이터 기록, 청킹 전략·임베딩·벡터 저장소 결정(임의 확정 금지).
