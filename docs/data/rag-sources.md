# RAG 출처 기준

## 출처 우선순위

1. 관련 법령 (주택임대차보호법 등)
2. 표준 주택임대차계약서
3. 공공기관 가이드 (국토교통부, 법무부, 대법원 등기, 지자체 등)

블로그·카페·커뮤니티 자료는 **핵심 근거로 사용하지 않는다.** RAG는 근거 검색·설명만 담당하고 판정을 내리지 않는다(판정은 규칙 엔진 담당, [`judgment-spec.md`](judgment-spec.md)).

## 필수 메타데이터

각 RAG 자료는 다음을 기록한다. (`data/rag/metadata/`)

| 필드 | 의미 |
|------|------|
| `document_title` | 자료명 |
| `institution` | 발행기관 |
| `article_or_section` | 조문·항목 (해당 시) |
| `effective_date` | 시행일 (법령·표준서식) |
| `source_url` | 원문 URL |
| `collected_date` | 수집일 |
| `document_type` | 문서 유형 (법령 / 표준계약서 / 공공기관 가이드 등) |
| `source_status` | `official_verified` / `synthetic_reference` / `unverified` / `excluded` |
| `verification_note` | 공식성·URL·발행기관·이용조건 검증 메모 |
| `source_sha256` / `content_sha256` | 로컬에 보존한 수집 원문 또는 정규화 원문의 SHA-256 |
| `metadata_sha256` | 원문과 구분되는 결정적 manifest 행 SHA-256 |
| `usage_terms` | 원문 저장·재배포·인용 가능 범위 |

- 법령·표준서식은 `effective_date`(시행일)를, 가이드는 최소 `collected_date`(수집일)를 기록한다.
- 조문 단위로 인용 가능하도록 `article_or_section`을 가능한 한 채운다(판정 근거 첨부에 사용).

## 데이터 분리

- 원본(`data/rag/sources`)·청크(`data/rag/chunks`)·메타데이터(`data/rag/metadata`)·검색 평가(`data/rag/evaluation`)를 분리한다.
- 근거가 없으면 판정을 유지하되 설명을 `근거 확인 필요`로 반환한다.
- `OfficialSource`와 `evidence_sources`에는 `official_verified`이면서 공식 원문 URL·발행기관이 확인된 자료만 포함한다.
- 합성 참고·미검증·제외 자료는 평가 구조 참고로만 유지하며 공식 근거로 노출하지 않는다.
- `rule_evidence_map.csv`와 dev/test retrieval goldset의 기대 source ID도 `official_verified`만 허용한다.

## 확정 (2026-07-14 선정표)

- 임베딩: gemini-embedding-001 + BM25 하이브리드, 재랭킹: Cohere rerank-v4.0-pro. (`../ai/model-routing.md`)
- 벡터 저장소: Chroma 로컬 모드.

## 2026-07-16 공식 출처 manifest

- 공식 검증 9개를 `data/rag/metadata/official_sources.jsonl`에 기록했다. `scripts/prepare_rag_sources.py`가 inventory에서 결정적으로 재생성한다.
- 국가법령정보센터는 저작권법 제7조 대상 법령정보와 법제처 보유 저작물의 자유이용 정책을 안내한다. 다만 서식·첨부물의 제3자 권리 가능성 때문에 개별 이용조건 확인 전 원문은 커밋하지 않는다.
- 법무부는 공공누리 표시가 있는 자료만 표시 조건에 따라 자유 이용하고, 표시가 없으면 사전 협의를 요구한다. 표준계약서 첨부물의 개별 표시를 확정하지 못해 원문을 저장하지 않는다.
- 국토교통부 체크리스트와 HUG 수시 갱신 상품 페이지도 링크·메타데이터만 사용한다.
- 따라서 현재 법령 2개는 `distribution_mode=local_source`와 `content_sha256`을 기록하고, 나머지 7개는 `metadata_only`, `content_sha256=null`이다. `metadata_sha256`을 원문 해시로 가장하지 않는다.

## 미정 (TODO)

- 기본 청킹 크기·중첩은 배치 1 로컬 구현에서 `1200`·`120`을 사용한다. 공식 코퍼스 수집 후 실제 문서 구조 평가를 거쳐 버전으로 확정한다.
- 출처 후보 15개는 `data/rules/source_inventory.csv`에서 상태 분류 완료. 명시적 재배포 허용을 확인한 원문만 수집한다.

## 2026-07-16 평가 계약 정비

- 기존 goldset에 포함됐던 합성 `SRC-REGISTRY-SAMPLE`, 미검증 `SRC-MORTGAGE-GUIDE`·`SRC-LEAFLET`, 제외 `SRC-REGISTRY-APPLY`를 공식 근거 정답에서 제거했다.
- 공식 대체 출처를 임의로 만들지 않았으며, 현재 검증된 source ID만 기대값으로 유지했다.
- 이 변경은 규칙 판정 정답을 변경하지 않는다. retrieval의 사용자 노출 근거 계약만 강화한다.
