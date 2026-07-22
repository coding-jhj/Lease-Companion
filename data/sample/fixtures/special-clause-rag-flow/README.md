# 특약 RAG AI 종단 합성 fixture

`cases.json`은 실제 개인정보가 없는 작업 7 오프라인 검증 입력이다.

- `matched_deferred_refund`: 결정론적 매칭 → J10 → 공식 근거 → 생성
- `normal_protective_clause`: 정상 보호 문구. 특약 카드를 만들지 않음
- `unmatched_pet_clause`: 카탈로그 미매칭. 새 판정을 만들지 않음
- `compound_repair_restoration`: 한 문장을 수리·원상복구 두 유형으로 연결
- `matched_without_evidence`: 매칭되지만 검색 근거가 없는 fallback 경계

`base_input_snapshot`의 확인 완료 snapshot에 위 문장들을 넣어 테스트한다. 실제 Gemini·Cohere 호출 없이 BM25와 Fake generation provider를 사용한다.
