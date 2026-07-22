# 특약별 공식근거 RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자가 확인한 특약 문장을 결정론적으로 R/J 판정에 연결하고, 그 특약 원문을 검색 질의에 포함해 직접 관련된 공식 근거·쉬운 설명·확인 질문·수정 요청 문구를 리포트 카드로 제공한다.

**Architecture:** 특약 분리와 카탈로그 매칭은 판정 입력 준비만 담당하고, 최종 상태와 시급도는 기존 Python 규칙 엔진이 결정한다. RAG는 판정 이후 특약 원문과 카탈로그가 제한한 공식 출처·섹션 안에서 근거를 검색·재정렬하며 판정을 변경하지 않는다. 생성 단계는 검색된 근거만 사용하고, Backend는 canonical 결과를 계약 건의 분석 실행에 저장하며, Frontend는 R/J 리포트 안에 별도의 `확인이 필요한 특약` 섹션으로 표시한다.

**Tech Stack:** Python 3, Pydantic canonical schema, 기존 Gemini embedding + BM25 + RRF + Cohere rerank, FastAPI, SQLAlchemy/PostgreSQL JSON, React + Vite + TypeScript, Vitest + Testing Library, pytest.

## Global Constraints

- `RuleStatus`와 `urgency`는 Python 규칙 엔진만 결정한다.
- 카탈로그와 RAG는 새 법률·안전·사기 판정을 만들거나 기존 R/J 판정을 변경하지 않는다.
- 사용자 표시 이름은 `확인이 필요한 특약` 또는 `특약별 근거와 요청 문구`를 사용하고, `불공정·무효·위법`을 확정 표현으로 사용하지 않는다.
- 카탈로그는 별도 판정 축을 만들지 않고 기존 `J09~J12`, `R08~R10`, `R18~R19` 중 명시된 ID에만 연결한다.
- 허용된 공식 원문에서 근거를 찾지 못하면 `evidence_sources=[]`를 유지한다.
- 실제 계약서나 개인정보를 평가·fixture 데이터로 커밋하지 않는다.
- 기존 `risk_patterns`는 DP01~DP08 피해 유형 비교 책임을 유지하며 특약 분류기로 재사용하지 않는다.
- Backend는 AI 도메인 타입을 중복 정의하지 않고 canonical Pydantic 모델을 import한다.
- 신규 패키지나 미정 기술을 추가하지 않는다.
- 구현 중 `git commit`과 `git push`는 사용자가 명시적으로 요청한 경우에만 수행한다.

---

## 현재 저장소 진단과 부족 자료

### 이미 재사용 가능한 것

- `ai/src/lease_companion_ai/extraction/minimum_mvp.py::_collect_special_clauses`: 특약 문장 분리 fallback.
- `DocumentExtraction.special_clauses`와 사용자 확인 스냅샷: 분석 전 확인된 특약 원문.
- `ai/src/lease_companion_ai/rules/judgments.py`: J09~J12 판정 경계.
- `ai/src/lease_companion_ai/rag/`: BM25·vector·RRF·rerank·공식 출처 allowlist·fallback.
- `ai/src/lease_companion_ai/generation/`: 근거 기반 설명·질문·행동과 guardrail.
- `AnalysisRun.result`·`generation_result`: 계약 건별 canonical JSON 저장·재조회.
- `frontend/src/features/evidence-sources/EvidenceDisclosure.tsx`: 공식 근거 표시의 공통 하위 UI.

### 구현 전에 보강해야 할 자료

1. **특약 카탈로그 정답 정의**: 유형 ID, 버전, 포함·제외 패턴, 연결 R/J, 허용 상태, 기본 시급도 출처, 허용 source/section, 설명 금지 표현이 없다.
2. **특약별 공식 근거 범위표**: 기존 allowlist는 R/J 단위이며, 개별 특약 유형이 어느 조·항·표준계약서 항목을 검색해야 하는지 없다.
3. **카탈로그 goldset**: 12개 양성 문장만으로는 부족하다. 정상 특약, 부정문, 예외조건, 한 문장에 두 논점이 있는 복합 특약, 표현을 바꾼 문장이 필요하다.
4. **retrieval goldset**: 특약 문장별 기대 `source_id`뿐 아니라 기대 `article_or_section` 또는 `chunk_id`가 없다.
5. **생성 goldset**: 설명·질문·수정 요청이 어떤 근거를 사용해야 하는지와 금지 문구 정답이 없다.
6. **canonical 특약 카드 스키마**: 특약 원문, 매칭 방식, 연결 R/J, 규칙 결과, 근거 청크, 생성 안내를 한 카드로 묶는 계약이 없다.
7. **현재 fixture의 대표 사례**: `case-001`은 전체 파이프라인 회귀용이므로 특약 RAG 성공·근거 없음·복합 특약을 대표하는 별도 합성 fixture가 필요하다.

## 목표 데이터 흐름

```text
사용자 확인 완료 special_clauses[]
  -> clause_id 부여 및 문장 정규화
  -> versioned catalog 후보 매칭
  -> 기존 R/J 규칙에 clause context 전달
  -> Python 규칙 결과(status/urgency) 확정
  -> actionable clause에 ClauseRetrievalQuery 생성
  -> catalog가 허용한 official source/section만 검색
  -> hybrid Top-20 -> rerank Top-5 -> source 중복 제거 Top-3
  -> 검색 근거 안에서 설명/질문/수정 요청 생성
  -> guardrail 및 source-id grounding 검사
  -> AnalysisRunResult.special_clause_reviews 저장
  -> 리포트 `확인이 필요한 특약` 카드 표시
```

---

### Task 1: 특약 카탈로그와 평가 계약 확정

**Files:**
- Create: `data/rules/special_clause_catalog.json`
- Create: `data/rules/special_clause_evidence_map.csv`
- Create: `data/evaluation/special-clauses/catalog_dev.jsonl`
- Create: `data/evaluation/special-clauses/catalog_test.jsonl`
- Create: `data/evaluation/special-clauses/retrieval_dev.jsonl`
- Create: `data/evaluation/special-clauses/retrieval_test.jsonl`
- Create: `data/evaluation/special-clauses/generation_cases.jsonl`
- Create: `docs/data/special-clause-catalog.md`
- Modify: `docs/data/rag-sources.md`
- Test: `ai/tests/special_clauses/test_catalog_contract.py`

**Interfaces:**
- Consumes: 기존 R/J ID, `official_sources.jsonl`, `RuleStatus`, `Urgency`.
- Produces: `load_special_clause_catalog() -> tuple[SpecialClauseCatalogEntry, ...]`가 읽을 버전 관리 데이터와 독립 평가셋.

- [ ] **Step 1: 카탈로그 계약 테스트 작성**

  `test_catalog_contract.py`에서 각 행에 `catalog_id`, `version`, `display_name`, `related_rule_ids`, `related_judgment_ids`, `include_patterns`, `exclude_patterns`, `allowed_source_sections`, `explanation_boundary`가 있고, R/J 및 source ID가 기존 명세에 존재하며, DP ID나 새 상태를 포함하지 않는지 검증한다.

- [ ] **Step 2: 실패 테스트 실행**

  Run: `cd ai; python -m pytest tests/special_clauses/test_catalog_contract.py -q`
  Expected: FAIL because catalog files do not exist.

- [ ] **Step 3: 최소 카탈로그 작성**

  첫 버전은 팀이 검증한 12개를 그대로 복사하지 말고 논점 기준으로 중복 제거한다. 최소 후보는 `SC-DEFERRED-REFUND`, `SC-REPAIR-SCOPE`, `SC-RESTORATION-SCOPE`, `SC-RIGHTS-CHANGE`, `SC-MANAGEMENT-FEE`, `SC-MAIN-SPECIAL-CONFLICT`로 시작한다. 각 항목은 기존 R/J만 참조하고 `allowed_source_sections`에 `source_id`와 실제 조·항/표준계약서 섹션을 기록한다.

- [ ] **Step 4: 블라인드 평가셋 작성**

  `catalog_test.jsonl`에는 개발 카탈로그 문장을 그대로 복사하지 않는다. 유형별로 양성 패러프레이즈, 정상 음성, 부정문, 조건 예외, 복합 문장을 넣고 기대 `catalog_ids`, `related_rule_ids`, `related_judgment_ids`를 기록한다. `retrieval_test.jsonl`에는 기대 source와 section을, `generation_cases.jsonl`에는 허용 핵심 의미와 `무효`, `위법`, `안전`, `사기` 금지 표현을 기록한다.

- [ ] **Step 5: 자료 책임 문서화 및 계약 테스트 통과**

  Run: `cd ai; python -m pytest tests/special_clauses/test_catalog_contract.py -q`
  Expected: PASS, with all referenced IDs and official sections resolvable.

**Review gate:** 법률 검토자가 카탈로그의 `allowed_source_sections`와 표현 경계를 승인하기 전 Task 4의 사용자 생성 문구를 운영 기본값으로 활성화하지 않는다.

---

### Task 2: Canonical 특약 검토 스키마 추가

**Files:**
- Modify: `ai/src/lease_companion_ai/schemas/unified.py`
- Modify: `ai/src/lease_companion_ai/schemas/__init__.py`
- Modify: `ai/tests/schemas/test_unified.py`
- Modify: `ai/tests/schemas/test_case001_fixture.py`
- Modify: `data/sample/fixtures/case-001/analysis_run_result.json`
- Modify: `data/sample/fixtures/case-001/generation_result.json`
- Modify: `data/schemas/README.md`
- Regenerate: `data/schemas/generated/analysis-run-result.schema.json`
- Regenerate: `data/schemas/generated/generation-result.schema.json`

**Interfaces:**
- Produces: `SpecialClauseReview`, `SpecialClauseGuidance`, `AnalysisRunResult.special_clause_reviews`, `GenerationResult.special_clause_items`.
- Consumes: 기존 `OfficialSource`, `RuleStatus`, `Urgency`와 R/J 식별자.

- [ ] **Step 1: 스키마 실패 테스트 작성**

  다음 불변성을 테스트한다: `clause_id`는 분석 실행 안에서 유일, `original_text`는 비어 있지 않음, `related_rule_ids`·`related_judgment_ids` 중 하나 이상 존재, `status`·`urgency`는 연결된 Python 결과와 일치, `evidence_sources`는 공식 출처만 허용, guidance가 참조하는 source ID는 같은 카드 근거의 부분집합.

- [ ] **Step 2: 실패 테스트 실행**

  Run: `cd ai; python -m pytest tests/schemas/test_unified.py tests/schemas/test_case001_fixture.py -q`
  Expected: FAIL because special-clause types are absent.

- [ ] **Step 3: 최소 canonical 타입 구현**

  `SpecialClauseReview`는 `clause_id`, `original_text`, `catalog_ids`, `match_method`(`catalog_exact|catalog_pattern|unmatched`), `related_rule_ids`, `related_judgment_ids`, `status`, `urgency`, `reason`, `triggers_actions`, `evidence_sources`, `limitations`를 가진다. `SpecialClauseGuidance`는 `clause_id`, `plain_explanation`, `confirmation_questions`, `revision_requests`, `source_ids`, `generation_method`를 가진다. 새 판정 상태나 별도 위험 점수는 만들지 않는다.

- [ ] **Step 4: fixture와 JSON Schema 재생성**

  기존 schema export 명령을 사용해 generated schema를 갱신하고 `case-001`에는 하위 호환을 확인할 최소 대표 카드만 추가한다.

- [ ] **Step 5: 스키마 검증 실행**

  Run: `cd ai; python -m pytest tests/schemas -q`
  Expected: PASS.

---

### Task 3: 특약 분리·카탈로그 후보 매칭 모듈 구현

**Files:**
- Create: `ai/src/lease_companion_ai/special_clauses/__init__.py`
- Create: `ai/src/lease_companion_ai/special_clauses/models.py`
- Create: `ai/src/lease_companion_ai/special_clauses/catalog.py`
- Create: `ai/src/lease_companion_ai/special_clauses/service.py`
- Create: `ai/tests/special_clauses/test_catalog_matching.py`
- Modify: `ai/src/lease_companion_ai/pipelines/classified_analysis.py`

**Interfaces:**
- Consumes: 사용자 확인 완료 `InputSnapshot`, `special_clause_catalog.json`.
- Produces: `match_special_clauses(snapshot: InputSnapshot) -> tuple[SpecialClauseCandidate, ...]`.

- [ ] **Step 1: 카탈로그 매칭 실패 테스트 작성**

  정확 문구, 패러프레이즈용 결정 패턴, 제외 패턴, 부정문, 복합 특약, 미매칭 문장을 포함한다. 하나의 문장에 여러 논점이 있으면 여러 catalog 후보를 허용하되 동일 ID 중복은 제거한다.

- [ ] **Step 2: 실패 테스트 실행**

  Run: `cd ai; python -m pytest tests/special_clauses/test_catalog_matching.py -q`
  Expected: FAIL because matching service is absent.

- [ ] **Step 3: 결정론적 후보 매칭 구현**

  입력은 반드시 사용자 확인 완료 값을 사용한다. 공백·구두점 정규화만 수행하고 법적 의미를 새로 생성하지 않는다. 카탈로그는 후보 R/J와 검색 범위를 선택하지만 `status`, `urgency`, `reason`을 반환하지 않는다.

- [ ] **Step 4: 분류 결과를 기존 규칙 입력 문맥에 연결**

  `classified_analysis.py`에서 후보를 J09~J12/R08~R10/R18~R19 실행 전에 준비하고, 규칙 엔진이 기존 명세에 따라 상태를 결정하도록 전달한다. `risk_patterns/service.py`는 수정하지 않는다.

- [ ] **Step 5: 매칭 및 기존 규칙 회귀 테스트 실행**

  Run: `cd ai; python -m pytest tests/special_clauses/test_catalog_matching.py tests/rules/test_classification_judgments.py tests/pipelines/test_classified_analysis.py -q`
  Expected: PASS with unchanged existing R/J outcomes except new clause linkage metadata.

---

### Task 4: 특약 원문 기반 검색·재정렬 구현

**Files:**
- Modify: `ai/src/lease_companion_ai/rag/models.py`
- Create: `ai/src/lease_companion_ai/rag/clause_service.py`
- Modify: `ai/src/lease_companion_ai/rag/service.py`
- Modify: `ai/src/lease_companion_ai/rag/indexing/chunker.py`
- Create: `ai/tests/rag/test_clause_retrieval.py`
- Modify: `ai/tests/rag/test_chunking.py`
- Modify: `ai/tests/rag/test_evidence_enrichment.py`
- Modify: `docs/ai/rag-design.md`

**Interfaces:**
- Produces: `ClauseRetrievalQuery`와 `enrich_special_clause_reviews(analysis, candidates) -> AnalysisRunResult`.
- Consumes: Task 1의 source/section allowlist, Task 2의 카드 타입, Task 3의 candidate.

- [ ] **Step 1: 원문이 검색 결과를 바꾸는 실패 테스트 작성**

  같은 J10 상태지만 `신규 임차인 입주`, `공제 후 반환`, `60일 후 반환` 세 문장이 서로 다른 검색 텍스트와 기대 section을 반환해야 한다. allowlist 밖 source, section 밖 청크, 비공식 출처, 근거 없음 케이스도 포함한다.

- [ ] **Step 2: 실패 테스트 실행**

  Run: `cd ai; python -m pytest tests/rag/test_clause_retrieval.py -q`
  Expected: FAIL because `ClauseRetrievalQuery` is absent.

- [ ] **Step 3: `ClauseRetrievalQuery` 구현**

  검색 텍스트는 `catalog display name + 연결 R/J 이름·상태 + 비식별 특약 원문`으로 구성한다. `allowed_source_sections`를 필수로 받고, source ID 필터 후 section 필터를 적용한다. 개인정보 제거로 문장 의미가 손상될 때는 원문 대신 구조화된 조건만 검색한다.

- [ ] **Step 4: 조·항/항목 보존 청킹 보강**

  법령은 조·항, 표준계약서는 개별 조항·특약, 체크리스트는 개별 항목 경계를 우선한다. 기존 1200/120 기본값은 일반 R/J 검색에 유지하고 특약 검색용 section 경계가 평가상 개선될 때만 청킹 버전을 올린다.

- [ ] **Step 5: 검색·재정렬·근거 없음 처리 구현**

  기존 hybrid Top-20과 rerank Top-5를 재사용하고, 최종 카드에는 source 중복을 제거한 Top-3를 연결한다. 유사도가 높아도 허용 section 밖이면 버리며, 결과가 없으면 빈 배열을 반환한다. R/J `status`, `urgency`, `reason` 전후 동일성을 assert한다.

- [ ] **Step 6: retrieval goldset 평가 실행**

  Run: `cd ai; python -m pytest tests/rag/test_clause_retrieval.py tests/rag/test_chunking.py tests/rag/test_evidence_enrichment.py -q`
  Expected: PASS and report source/section Top-3 recall separately; do not invent a target threshold before measurement.

---

### Task 5: 근거 기반 특약 설명·질문·수정 요청 생성

**Files:**
- Create: `ai/prompts/generation/special_clause_guidance_v1.txt`
- Modify: `ai/src/lease_companion_ai/generation/service.py`
- Modify: `ai/src/lease_companion_ai/providers/generation.py`
- Modify: `ai/src/lease_companion_ai/providers/gemini_generation.py`
- Modify: `ai/src/lease_companion_ai/guardrails/grounding.py`
- Create: `ai/tests/generation/test_special_clause_guidance.py`
- Modify: `ai/tests/generation/test_generation_service.py`
- Modify: `docs/ai/prompt-management.md`

**Interfaces:**
- Produces: `generate_special_clause_guidance(review: SpecialClauseReview) -> SpecialClauseGuidance`.
- Consumes: Task 4에서 근거가 연결된 카드만 provider 생성 대상으로 사용한다.

- [ ] **Step 1: grounding·금지표현 실패 테스트 작성**

  설명과 요청 문구가 카드의 `source_ids` 밖 근거를 참조하지 못하고, `무효다`, `위법이다`, `안전하다`, `사기다` 등의 단정 표현을 거부하는지 테스트한다. 근거 없음에서는 법적 설명을 생성하지 않고 확인 질문 템플릿만 반환해야 한다.

- [ ] **Step 2: 실패 테스트 실행**

  Run: `cd ai; python -m pytest tests/generation/test_special_clause_guidance.py -q`
  Expected: FAIL because clause guidance generation is absent.

- [ ] **Step 3: 버전 프롬프트 및 provider 계약 구현**

  출력은 `plain_explanation`, `confirmation_questions`, `revision_requests`, `source_ids`로 제한한다. `표준계약서와 다르다`와 `법에 위반된다`를 동일 의미로 취급하지 않도록 명시한다. R/J 상태와 시급도를 입력으로 제공하되 변경 필드는 출력에 두지 않는다.

- [ ] **Step 4: 안전한 결정론적 fallback 구현**

  provider 실패 시 카탈로그에 승인된 템플릿이 있는 유형만 템플릿 안내를 반환한다. 승인 템플릿이 없거나 근거가 없으면 `공식 근거를 확인하지 못해 문구 수정을 단정해 안내하지 않습니다`와 구체적인 확인 질문만 반환한다.

- [ ] **Step 5: guardrail과 generation goldset 실행**

  Run: `cd ai; python -m pytest tests/generation/test_special_clause_guidance.py tests/generation/test_generation_service.py -q`
  Expected: PASS with zero prohibited assertions in the fixture set.

---

### Task 6: AI 파이프라인 통합과 종단 평가

**Files:**
- Modify: `ai/src/lease_companion_ai/pipelines/classified_analysis.py`
- Modify: `ai/tests/pipelines/test_classified_analysis.py`
- Create: `ai/tests/pipelines/test_special_clause_e2e.py`
- Create: `data/sample/fixtures/special-clause-rag/contract_extraction.json`
- Create: `data/sample/fixtures/special-clause-rag/input_snapshot.json`
- Create: `data/sample/fixtures/special-clause-rag/analysis_run_result.json`
- Create: `data/sample/fixtures/special-clause-rag/generation_result.json`
- Modify: `docs/architecture/ai-pipeline.md`

**Interfaces:**
- Produces: Backend가 그대로 저장할 완성된 `AnalysisRunResult`와 `GenerationResult`.

- [ ] **Step 1: 종단 실패 테스트 작성**

  합성 계약에 매칭 특약, 정상 특약, 미매칭 특약, 복합 특약을 넣는다. 기대 카드는 actionable한 기존 R/J 결과와 연결되고, 정상·미매칭 특약은 판정을 만들어내지 않으며, 근거와 guidance의 source ID가 일치해야 한다.

- [ ] **Step 2: 실패 테스트 실행**

  Run: `cd ai; python -m pytest tests/pipelines/test_special_clause_e2e.py -q`
  Expected: FAIL before pipeline orchestration is connected.

- [ ] **Step 3: 파이프라인 순서 연결**

  `사용자 확인 snapshot -> catalog candidate -> Python R/J -> clause RAG -> generation -> guardrail` 순서를 고정한다. RAG/provider 실패가 규칙 분석 전체를 실패시키지 않게 한다.

- [ ] **Step 4: AI 전체 회귀 실행**

  Run: `cd ai; python -m pytest tests/special_clauses tests/rag tests/generation tests/pipelines/test_special_clause_e2e.py tests/pipelines/test_classified_analysis.py -q`
  Expected: PASS.

---

### Task 7: Backend 저장·API 계약 동기화

**Files:**
- Modify: `backend/app/workers/analysis.py`
- Modify: `backend/app/schemas/analysis.py`
- Modify: `backend/tests/api/test_analyses.py`
- Modify: `backend/tests/api/test_case001_e2e.py`
- Create: `backend/tests/api/test_special_clause_report.py`
- Modify: `backend/scripts/export_openapi.py` only if export coverage needs the new canonical fields
- Regenerate: `docs/api/openapi.json`
- Modify: `docs/api/data-contract-v1.md`
- Modify: `docs/api/api-overview.md`

**Interfaces:**
- Consumes: Task 6 canonical JSON.
- Produces: 기존 `GET /api/contracts/{contract_id}/analysis-runs/{analysis_run_id}` 응답의 `result.special_clause_reviews`와 `generation_result.special_clause_items`.

- [ ] **Step 1: API 저장·재조회 실패 테스트 작성**

  분석 완료 후 특약 원문·R/J 연결·근거·guidance가 같은 `analysis_run_id`로 저장되고 재조회 후 canonical Pydantic 검증을 통과하는지 테스트한다. 다른 사용자의 contract 접근 차단과 분석 중 `null` 상태도 유지한다.

- [ ] **Step 2: 실패 테스트 실행**

  Run: `cd backend; python -m pytest tests/api/test_special_clause_report.py -q`
  Expected: FAIL before worker/API serialization is updated.

- [ ] **Step 3: Worker 저장 경계 갱신**

  별도 테이블을 만들지 않고 기존 `AnalysisRun.result`·`generation_result` JSON에 canonical 필드를 저장한다. 특약 원문을 로그나 오류 메시지에 기록하지 않는다. 생성 실패 시 `special_clause_reviews`는 유지하고 `special_clause_items`만 비어 있게 한다.

- [ ] **Step 4: API·OpenAPI 동기화**

  기존 분석 상세 endpoint를 유지하며 독립 results endpoint를 추가하지 않는다. OpenAPI와 `data-contract-v1.md`에 빈 배열·근거 없음·생성 실패 동작을 명시한다.

- [ ] **Step 5: Backend 회귀 실행**

  Run: `cd backend; python -m pytest tests/api/test_special_clause_report.py tests/api/test_analyses.py tests/api/test_case001_e2e.py -q`
  Expected: PASS.

---

### Task 8: Frontend 특약 카드와 리포트 통합

**Files:**
- Modify: `frontend/src/types/api.ts`
- Create: `frontend/src/features/special-clause-reviews/SpecialClauseReviewSection.tsx`
- Create: `frontend/src/features/special-clause-reviews/SpecialClauseCard.tsx`
- Create: `frontend/tests/features/special-clause-review-section.test.tsx`
- Modify: `frontend/src/pages/result-report/ResultReportPage.tsx`
- Modify: `frontend/src/features/result-report/ReportPrintSheet.tsx`
- Modify: `frontend/tests/pages/result-report.test.tsx`
- Modify: `frontend/src/styles/global.css`
- Modify: `frontend/src/features/README.md`

**Interfaces:**
- Consumes: Backend `AnalysisRunDetailDto`의 두 신규 배열.
- Produces: 화면과 인쇄 리포트의 `확인이 필요한 특약` 섹션.

- [ ] **Step 1: 컴포넌트 실패 테스트 작성**

  카드는 원문, 확인 우선순위, 쉬운 설명, 공식 근거, 확인 질문, 수정 요청 문구를 표시해야 한다. 근거 없음, generation 없음, 긴 특약, 동일 source 중복, 빈 카드 목록을 테스트한다. `위험 특약`, `무효 특약` 같은 단정 레이블이 없어야 한다.

- [ ] **Step 2: 실패 테스트 실행**

  Run: `cd frontend; npm test -- --run tests/features/special-clause-review-section.test.tsx`
  Expected: FAIL because the feature does not exist.

- [ ] **Step 3: 타입과 카드 구현**

  Backend/OpenAPI 필드명과 동일한 DTO를 추가한다. `EvidenceDisclosure`는 공식 근거 하위 표시로 재사용하되 `DamagePatternTable`은 재사용하지 않는다. 원문에서 카탈로그가 매칭한 구간만 강조하고, 색상 외 문구·아이콘으로 우선순위를 표시한다.

- [ ] **Step 4: 리포트·인쇄 통합**

  `ResultReportPage`의 기존 R/J 우선순위 섹션 뒤, 피해유형 비교 앞에 특약 섹션을 둔다. 카드가 없으면 섹션 전체를 숨기고, 근거가 없으면 `관련 공식 근거를 찾지 못했습니다`를 표시한다. 인쇄 리포트에도 같은 정보와 URL을 포함한다.

- [ ] **Step 5: 접근성·모바일 회귀 실행**

  Run: `cd frontend; npm test -- --run tests/features/special-clause-review-section.test.tsx tests/pages/result-report.test.tsx tests/features/evidence-disclosure.test.tsx`
  Expected: PASS with accessible headings and disclosure controls.

---

### Task 9: 전체 검증·문서·데모 증거 완성

**Files:**
- Modify: `docs/planning/user-flow.md`
- Modify: `docs/planning/mvp-scope.md`
- Modify: `docs/ai/evaluation-matrix.md`
- Create: `docs/decisions/2026-07-22-special-clause-evidence-rag.md`
- Create: `docs/meetings/2026-07-22-special-clause-rag-plan.md`
- Modify: `data/rag/evaluation/README.md`

**Interfaces:**
- Produces: 구현 상태, 측정 결과, 한계, 데모 시나리오가 일치하는 최종 인수 자료.

- [ ] **Step 1: 평가 지표 실행 및 실측 기록**

  catalog exact match, 유형별 precision/recall, 정상 특약 오탐, source Top-3 recall, section Top-3 recall, 비공식 출처 노출, 금지 단정 표현, source grounding 위반을 각각 기록한다. 목표 수치는 측정 전에 만들지 않는다.

- [ ] **Step 2: 전체 테스트 실행**

  Run: `cd ai; python -m pytest -q`
  Expected: PASS.

  Run: `cd backend; python -m pytest -q`
  Expected: PASS.

  Run: `cd frontend; npm test -- --run`
  Expected: PASS.

- [ ] **Step 3: 데모 시나리오 검증**

  동일 J10에 연결되는 서로 다른 특약 3개가 서로 다른 검색 질의·근거 section·요청 문구를 내는지 보여준다. 근거 없는 문장에서는 빈 근거와 제한 안내가 나오는지 함께 보여 RAG가 판정을 대신하지 않음을 증명한다.

- [ ] **Step 4: 문서와 실제 구현 상태 동기화**

  구현되지 않은 유료 provider 실측은 완료로 쓰지 않는다. 기존 R/J와 DP 축, 특약 카탈로그의 후보 역할, RAG의 근거 역할을 ADR에 명확히 분리한다.

- [ ] **Step 5: 최종 작업트리 점검**

  Run: `git status --short`
  Expected: only intended source, test, fixture, generated schema, OpenAPI, and documentation files are changed; no Chroma index, real contract, secrets, or unrelated generated files.

## 권장 실행 순서와 병렬화 경계

1. **반드시 선행:** Task 1 자료 계약 → Task 2 canonical 스키마.
2. **AI 핵심 순차:** Task 3 후보 매칭 → Task 4 특약 RAG → Task 5 생성 → Task 6 파이프라인.
3. **스키마 확정 후 병렬 가능:** Task 7 Backend와 Task 8 Frontend mock 구현. 실제 연결 검증은 Task 7 완료 후 수행한다.
4. **마지막:** Task 9 종단 검증과 문서 동기화.

## 인수 기준

- 같은 R/J 상태라도 특약 원문이 다르면 검색 질의와 관련 근거 section이 달라진다.
- 카탈로그 미매칭은 새 판정을 만들지 않는다.
- RAG 검색 전후 모든 R/J `status`, `urgency`, `reason`이 동일하다.
- 허용 source/section 밖의 유사 청크는 사용자에게 노출되지 않는다.
- 근거가 없을 때 빈 배열과 명시적 한계가 표시된다.
- 생성 안내가 참조하는 source ID는 해당 특약 카드 근거의 부분집합이다.
- Backend 재조회와 Frontend mock이 같은 canonical 형태를 사용한다.
- 모바일 리포트에서 특약 원문 → 설명 → 공식 근거 → 질문 → 수정 요청 흐름이 한 카드에서 이해된다.
- 기존 R01~R24, J01~J12, DP01~DP08 결과와 저장 결과의 하위 호환 회귀 테스트가 통과한다.

## 계획 자체 검토 결과

- 이미지의 7단계 모두 Task 3~8에 대응한다.
- 부족 자료는 Task 1, 스키마 공백은 Task 2에서 선행 해소한다.
- `risk_patterns`를 특약 카탈로그로 오용하지 않는다.
- 의미검색은 판정 폴백이 아니라 근거 검색으로만 사용한다.
- AI·Backend·Frontend가 공유하는 필드명은 Task 2의 canonical 타입으로 단일화한다.
