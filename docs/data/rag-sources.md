# RAG 출처 기준

## 출처 우선순위

1. 관련 법령 (주택임대차보호법 등)
2. 표준 주택임대차계약서
3. 공공기관 가이드 (국토교통부, 법무부, 지자체 등)

블로그·카페·커뮤니티 자료는 **핵심 근거로 사용하지 않는다.**

## 메타데이터 기준

각 RAG 자료는 다음을 기록한다. (`data/rag/metadata/`)

| 필드 | 의미 |
|------|------|
| `institution` | 기관명 |
| `document_title` | 문서명 |
| `url` | 출처 URL |
| `published_or_checked_date` | 발행일 또는 확인일 |

## 원칙

- 원본(`data/rag/sources`)·청크(`data/rag/chunks`)·메타데이터(`data/rag/metadata`)를 분리한다.
- RAG는 근거 검색·설명만 담당한다. 판정을 내리지 않는다.

## 미정 (TODO)

- 청킹 전략, 임베딩 모델, 벡터 저장소, 실제 출처 목록
