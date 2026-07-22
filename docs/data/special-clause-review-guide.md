# 특약 RAG 데이터 사람 검토 가이드

특약별 공식근거 RAG(플랜: `docs/planning/special-clause-evidence-rag-implementation-plan.md`)의
**세 가지 사람 검토 게이트**와 검토 방법을 정의한다. 이 검토를 통과하기 전에는 성능 수치를
"검증됨"으로 표기하지 않고, 운영 기본값으로 활성화하지 않는다.

검토 대상 초안:
- 카탈로그: `data/rules/special_clause_catalog.json` (review_status: unverified)
- 근거 범위표: `data/rules/special_clause_evidence_map.csv` (review_status 열: unverified)
- 평가셋: `data/evaluation/special-clauses/*.jsonl` (draft_pending_human_review)

---

## 게이트 A — 법률 검토 (카탈로그 + 근거 범위표)

**누가**: 주택임대차보호법·표준계약서·민법 조문을 직접 읽고 판단할 수 있는 사람.
**대상**: `special_clause_catalog.json`, `special_clause_evidence_map.csv`.

### 체크리스트 (유형 6개 각각)
- [ ] `related_judgment_ids`·`related_rule_ids`가 그 특약 유형의 논점과 맞는가? (허용 ID: J09~J12, R08~R10, R18~R19)
- [ ] `allowed_source_sections`의 **조·항이 실제로 그 논점의 근거인가?** 원문 대조:
  - `data/rag/sources/SRC-HTA-LAW.txt`(주임법), `SRC-STD-LEASE.txt`(표준계약서), `SRC-CIVIL-LEASE.txt`(민법 615/623/654), `SRC-CONFIRM-FORM.txt`(확인설명서), `SRC-MOLIT-CHECKLIST.txt`
  - 특히 주임법 **제10조(강행규정)** 인용이 과도하지 않은지(모든 유형에 붙일 근거는 아님)
- [ ] `explanation_boundary.prohibited_terms`에 `무효/위법/안전/사기`가 있는가? (단정 금지)
- [ ] 빠진 근거가 있는가? (예: 원상복구에 민법 제615조·제654조 준용 관계가 필요)

### 결과 기록
- 각 행의 `review_status`를 `unverified` → `verified` 또는 `rejected(사유)`로 바꾼다.
- 조·항 수정이 필요하면 CSV/JSON을 직접 고치고 사유를 커밋 메시지에 남긴다.

---

## 게이트 B — 블라인드 평가셋 검토 (핵심)

**누가**: **카탈로그를 만들지 않은 사람**(독립성). 이상적으로는 test 문장을 새로 써서 교체.
**왜**: 카탈로그와 평가셋을 같은 주체가 만들면 순환이라 측정이 무의미하다.
**대상**: `data/evaluation/special-clauses/catalog_test.jsonl`, `retrieval_test.jsonl`, `generation_cases.jsonl`.

### 체크리스트
- [ ] **라벨 정확성**: 각 문장의 `expected_catalog_ids`가 사람 판단과 일치하는가?
- [ ] **누출 없음**: `catalog_test`의 문장이 `catalog_dev`와 같지 않은가? (패러프레이즈여야 함)
- [ ] **5범주 커버**: 유형마다 positive_paraphrase / normal_negative / negation / conditional_exception / compound가 있는가? (현재 초안은 일부 유형만 5범주를 채움 — 부족분 추가)
- [ ] **어려운 케이스**: 부정문("~하지 않는다"), 예외("관계없이"), 복합문(한 문장 2논점), 표현 변형이 충분한가? AI가 놓칠 만한 문장을 사람이 추가
- [ ] **retrieval_test**: 문장별 `expected_source_ids`·`expected_sections`가 근거 범위표와 맞는가? 근거 없음 케이스도 있는가?
- [ ] **generation_cases**: `allowed_core_meaning`이 근거를 넘어서 단정하지 않는가? 금지 표현 목록이 맞는가?

### 참고: 현재 초안이 아는 약점 (검토 시 이 부분 집중)
초안 카탈로그를 평가셋에 돌린 sanity 결과, 다음 3건에서 카탈로그 패턴이 약하다(품질 지표 아님, 개선 지점):
1. 조건 예외("요청하면 먼저 반환")를 반환 연동으로 오탐
2. 복합문("입주 후 반환 + 원상복구비 부담")에서 두 논점 다 놓침
3. 권리변동("설정될 근저당…이의 제기")을 미탐

→ 이건 **Task 3 매칭 서비스에서 패턴을 고칠 몫**이다. 검토자는 **평가셋 라벨이 맞는지**만 판단하고, 카탈로그 패턴을 억지로 평가셋에 맞추지 않는다.

### 결과 기록
- 라벨을 고치거나 문장을 추가/교체하고, `README.md`의 `review_status`를 `human_reviewed`로 바꾼다.
- 검토자·검토일을 커밋 메시지에 남긴다.

---

## 게이트 C — 최종 인수 (측정·활성화)

게이트 A·B 통과 **후에만** 수행한다.
- [ ] Task 9 평가 실행: catalog exact match, 유형별 precision/recall, 정상 특약 오탐, source/section Top-3 recall, 비공식 출처 노출, 금지 단정 표현, source grounding 위반 — **실측만 기록(목표 수치 사전 생성 금지)**
- [ ] 법률 검토(A) 통과 전에는 사용자 생성 수정 문구를 운영 기본값으로 활성화하지 않는다
- [ ] ADR에 R/J·DP 축과 특약 카탈로그(후보 역할)·RAG(근거 역할) 분리를 기록

---

## 요약: 무엇을 지금, 무엇을 검토 후에
| 작업 | 사람 검토 필요? |
|------|----------------|
| 코드 구현(Task 3 매칭 ~ 8 프론트) | ❌ 지금 빌드 가능(성능은 미검증 표기) |
| chroma 재인덱싱 | ❌ 빌드 단계 |
| 성능 측정·인수(Task 9) | ✅ 게이트 B 후 |
| 운영 기본값 활성화 | ✅ 게이트 A + B 후 |
