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

- 법령·표준서식은 `effective_date`(시행일)를, 가이드는 최소 `collected_date`(수집일)를 기록한다.
- 조문 단위로 인용 가능하도록 `article_or_section`을 가능한 한 채운다(판정 근거 첨부에 사용).

## 데이터 분리

- 원본(`data/rag/sources`)·청크(`data/rag/chunks`)·메타데이터(`data/rag/metadata`)·검색 평가(`data/rag/evaluation`)를 분리한다.
- 근거가 없으면 판정을 유지하되 설명을 `근거 확인 필요`로 반환한다.
- `OfficialSource`와 `evidence_sources`에는 `official_verified`이면서 공식 원문 URL·발행기관이 확인된 자료만 포함한다.
- 합성 참고·미검증·제외 자료는 평가 구조 참고로만 유지하며 공식 근거로 노출하지 않는다.

## 확정 (2026-07-14 선정표)

- 임베딩: gemini-embedding-001 + BM25 하이브리드, 재랭킹: Cohere rerank-v4.0-pro. (`../ai/model-routing.md`)
- 벡터 저장소: Chroma 로컬 모드.

## 미정 (TODO)

- 청킹 크기·중첩·결정적 `chunk_id` 규칙은 구현 전 확정 필요.
- 출처 후보 15개는 `data/rules/source_inventory.csv`에서 상태 분류 완료. 원문 수집은 이용조건 확인 후 진행한다.
