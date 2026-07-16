# RAG 출처 메타데이터

`official_sources.jsonl`은 `scripts/prepare_rag_sources.py`가
`data/rules/source_inventory.csv`의 `official_verified` 행에서 결정적으로 생성한다.

- `metadata_sha256`: 해당 manifest 행의 무결성 해시
- `content_sha256`: 재배포가 명시적으로 허용되어 로컬에 저장한 원문의 해시
- `distribution_mode=metadata_only`: 원문을 저장하지 않고 공식 URL만 참조

`metadata_sha256`을 원문 해시로 해석하지 않는다.
