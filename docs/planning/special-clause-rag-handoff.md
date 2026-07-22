# 특약별 공식근거 RAG — 인수인계 문서

작성일: 2026-07-22. 다음 담당자가 이어서 진행하기 위한 현재 상태·남은 작업·주의사항 정리.

## 0. 먼저 읽을 문서
- 구현 플랜(단일 기준): [`special-clause-evidence-rag-implementation-plan.md`](special-clause-evidence-rag-implementation-plan.md)
- 사람 검토 방법: [`../data/special-clause-review-guide.md`](../data/special-clause-review-guide.md)
- 이 문서: 어디까지 됐고, 무엇을 이어서 할지.

## 1. 핵심 원칙 (절대 어기지 말 것)
- **RuleStatus·urgency는 Python 규칙 엔진만 결정.** 카탈로그·매칭·RAG는 판정을 만들거나 바꾸지 않는다.
- AI는 `무효/위법/안전/사기`를 **단정하지 않는다.** "표준계약서·법 기준과 다르니 확인·수정 요청" 형태로만.
- RAG 근거 없으면 `evidence_sources=[]` 유지.
- 데이터 자산은 **법률 검토(게이트 A)·블라인드 검토(게이트 B) 통과 전 `unverified`/`draft`** 표기 유지. 성능 수치는 검토 전 "미검증".

---

## 2. 완료된 작업 (테스트 통과)
전체: **AI 667 · Backend 16(회귀) · Frontend 100** 통과 기준.

| 플랜 Task | 상태 | 산출물 |
|-----------|------|--------|
| Task 2 — canonical 스키마 | ✅ 완료 | `SpecialClauseReview`·`SpecialClauseGuidance`, `AnalysisRunResult.special_clause_reviews`, `GenerationResult.special_clause_items` (`ai/src/lease_companion_ai/schemas/unified.py`) |
| Task 3 Step 1~3 — 결정론적 매칭 | ✅ 완료 | `ai/src/lease_companion_ai/special_clauses/` (models·catalog·service) |
| Task 3 Step 4 — 파이프라인 연결 | ✅ 완료 | `pipelines/classified_analysis.py::attach_special_clause_reviews` — 매칭 후보를 R/J 결과에 연결(status/urgency는 규칙 결과 반영, 근거는 비움) |
| Task 1 데이터 자산 | ⚠ 초안 | 아래 3절 |
| Task 4~9 | ❌ 미착수 | 아래 5절 |

---

## 3. "부족 자료 4가지" 상태
Codex가 지적한 4가지 부족 자료 — **전부 초안 완료**, 단 검토·수정 필요.

| # | 자료 | 파일 | 상태 |
|---|------|------|------|
| 1 | 특약 카탈로그 정답 정의 | `data/rules/special_clause_catalog.json` | 초안 ✅ / **게이트 A 검토로 구조 수정 필요**(4절) |
| 2 | 유형별 공식 근거 조·항 범위 | `data/rules/special_clause_evidence_map.csv` | 초안 ✅ / **게이트 A 반영 필요**(4절) |
| 3 | 블라인드 평가셋 | `data/evaluation/special-clauses/*.jsonl` | 초안 ✅ / **게이트 B(독립 검토) 미완** |
| 4 | canonical 스키마 | `unified.py` | ✅ 완료(수정 불필요) |

민법 코퍼스 공백도 해소: `data/rag/sources/SRC-CIVIL-LEASE.txt`에 제536·615·623·626·654조 발췌(형식·manifest 정합 검증 완료).

---

## 4. 게이트 A(법률 검토) 결과 — 반영해야 할 작업
담당자가 원문 대조 검토를 완료함. **핵심 문제: "문구가 명확한가"(명확성)와 "그 조건이 임차인에게 불리한가"(불리조건 탐지)가 R08·R09·R18에서 섞여 있음.** 명확하게 불리한 특약이 오히려 "명확=정상"으로 처리될 수 있음.

### 4-1. 구조 수정 (스키마·규칙까지 손대는 큰 작업)
1. **R08 분리**: `반환조건 명확성` vs `제3자·미래사건 연동 위험`(신규 임차인 입주·주택 매각·자금 사정 연동). 신규 규칙이 어려우면 R08에 하위 필드 `clarity`/`deferred_condition`/`tenant_risk` 추가.
2. **R09 분리**: `수리 책임`(계약 존속 중) vs `원상복구 범위`(계약 종료 시, 통상손모 포함 여부). J11도 `repair_responsibility`/`restoration_responsibility`로 하위 분리 권장.
3. **R10 vs R19 역할 분리**: R10=계약서에 담보권 설정 제한 특약 유무(문구 확인), R19=계약~잔금/입주 사이 실제 등기 권리변동(시점별 등기부 교차검증). 지금은 둘 다 "특약 유무"만 봐서 중복.
4. **J12 대응 R 규칙 신설**: 본문-특약 상충 탐지(동일 주제의 날짜·금액·반환조건·책임주체 상이). 판정은 "어느 조건이 적용되는지 불명확 → 확인 필요"까지만.
5. (참고) SC 유형이 R을 통해 실행되는 구조라면 **J03·J06·J07·J08·J12는 실행 R 규칙이 없음** — 실행 경로 점검 필요.

### 4-2. evidence_map 수정 (데이터만 — 바로 반영 가능)
| 유형 | 반영할 것 |
|------|-----------|
| DEFERRED-REFUND | **민법 제536조(동시이행) 직접 근거 추가**, 주임법 제4조는 **제2항(보호 규정)으로 정정·보조 근거화**, 제10조는 조건부로 강등, 동시이행 대법원 판례는 reference_cases로 |
| REPAIR-SCOPE | **민법 제626조 추가**, 표준계약서 **제4조 제2~4항** 추가, "주요설비=무조건 임대인" 대신 "사용·수익에 필요한 설비의 노후·불량 수리 포괄 전가" 탐지로 |
| RESTORATION-SCOPE | **제10조 제거**, 표준계약서 제9조 단서(통상손모·노후 제외)를 핵심 근거로 유지, 민법 615·654 유지 |
| RIGHTS-CHANGE | 제3조·제3조의2는 "위험 발생 이유"로, **표준계약서 특약사항(SRC-STD-LEASE 49~50행)·안심체크리스트(SRC-MOLIT-CHECKLIST 43·46·58행)를 "권장 확인·특약 근거"로 명시** |
| MANAGEMENT-FEE | 지금 근거로는 "임의 변경"보다 **"관리비·추가비용 명확성"**이 정확. 유형명 정리(`SC-MANAGEMENT-FEE-CLARITY`) 또는 변경권한 필드 추가. 확인·설명서 관리비 항목(SRC-CONFIRM-FORM 25~31행) 유지 |
| MAIN-SPECIAL-CONFLICT | "본문 전반" 대신 **상충 주제별 동적 근거 연결**(보증금→표준9조·민법536 / 수리→표준3·4조·민법623 / 원상복구→표준9조·민법615·654 / 관리비→표준1조·확인설명서 / 임대차기간→표준2조·주임법4 / 권리변동→표준특약·주임법3·3의2) |

### 4-3. 주임법 제10조(강행규정) 조건부화 (데이터만)
지금 3개 유형에 공통으로 붙어 있음 → **남용.** 제10조는 "임차인 불리 약정은 무조건 무효"가 아니라, **①구체적 주임법 조항 위반 + ②임차인에게 불리** 두 조건이 모두 확인될 때만 검토하는 보조 근거. `primary_basis`에서 빼고 다음 구조로:
```json
"legal_effect_review": {
  "hta_article_10_applicable": "undetermined",
  "requires_specific_hta_violation": true,
  "court_or_expert_review_needed": true
}
```

### 4-4. 금지/권장 표현 (생성 단계 guardrail·explanation_boundary)
| 피할 표현 | 권장 표현 |
|-----------|-----------|
| 무효인 특약입니다 | 효력이 제한될 가능성이 있어 별도 확인이 필요합니다 |
| 불법입니다 | 관련 법령과 충돌할 가능성이 있습니다 |
| 안전한 계약입니다 | 현재 제출된 문서에서 해당 항목은 확인되었습니다 |
| 반드시 임대인이 부담합니다 | 임대인의 수선의무 범위에 해당할 가능성이 있습니다 |

추가 금지: `법적으로 문제없음`, `보증금이 보호됨`, `반드시 돌려받을 수 있음`, `계약해도/하면 안 됨`, `전세사기 확정`, `임대인의 범죄`.

### 4-5. reference_cases로 분리할 판례 (별도 자료)
- DEFERRED: 보증금 반환·목적물 반환 동시이행 판례
- REPAIR: 민법 제623조 수선 범위(사소한 수선 vs 사용·수익 방해 수선) 판례
법령 발췌 파일에 넣지 말 것 — `reference_cases` 계열로 공식 근거와 분리.

---

## 5. 남은 Task (미착수)
| Task | 내용 | 의존 |
|------|------|------|
| Task 4 | 특약 원문 기반 RAG 검색·재정렬(`rag/clause_service.py`), 조·항 단위 청킹 보강 | evidence_map 확정 후가 안전 |
| Task 5 | 근거 기반 특약 설명·질문·수정요청 생성 + guardrail(금지표현) | Task 4 |
| Task 6 | 파이프라인 종단(catalog→R/J→clause RAG→generation→guardrail) + 전용 fixture | Task 4·5 |
| Task 7 | Backend 저장·API(`special_clause_reviews`/`special_clause_items` 응답) | Task 6 |
| Task 8 | Frontend `확인이 필요한 특약` 섹션(7번 리포트) | Task 7 스키마 확정 후 병렬 |
| Task 9 | 종단 평가·실측·문서·ADR | 전부 + 게이트 B |

### chroma 재인덱싱
민법 등 새 출처가 실제 검색되려면 인덱스 재빌드 필요(임베딩 호출 → API 키/오프라인 BM25). Task 4에서 처리.

---

## 6. 다음 담당자 착수 우선순위 (권장)
1. **evidence_map 수정(4-2) + 제10조 조건부화(4-3)** — 데이터만, 바로 가능. 저위험.
2. **게이트 B(평가셋 독립 검토)** — 카탈로그를 안 만든 사람이 `catalog_test.jsonl` 라벨 검증·5범주 보강. 코드 안 막음, 병렬 가능.
3. **카탈로그/규칙 구조 변경(4-1)** — R08/R09/R10/R19 분리·J12 R 규칙. 스키마·`ALLOWED_RULE_STATUSES`·`judgments.py`·매칭 패턴·테스트까지 손감. **가장 큰 작업**, 구조 확정 후 착수.
4. Task 4(특약 RAG) → 5 → 6 → 7 → 8 → 9.

> 원칙: 코드는 검토 전에도 빌드 가능하나, **성능은 "미검증" 표기**, **운영 활성화는 게이트 A·B 후.**

---

## 7. 운영 팁 (Windows 환경)
- 테스트 실행: `conda run`이 한글 출력에서 깨짐 → `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 <env>/python.exe -m pytest ...` 직접 호출.
- **새 RAG 출처 추가 시**: ① `.txt`를 `data/rag/sources/`에 LF·1조=1줄로 ② `source_inventory.csv`에 1행(콤마 없는 필드만) ③ `python scripts/prepare_rag_sources.py`로 manifest 재생성(해시 자동) ④ `test_source_manifest.py`의 하드코딩 local 집합 갱신.
- **autocrlf 주의**: `data/rag/sources/*.txt`는 `.gitattributes`가 `eol=lf`로 고정. CSV/JSONL 편집 시 utf-8-sig 재작성은 BOM·인용부호 churn·`test_source_contract` 파손 유발 → **바이트 단위 치환** 권장.
- `data/rag/index/chroma/`는 커밋 제외(대용량 인덱스).

## 8. 파일 지도
```
ai/src/lease_companion_ai/
  schemas/unified.py                         # SpecialClauseReview·Guidance (Task 2)
  special_clauses/{models,catalog,service}.py# 결정론적 매칭 (Task 3)
  pipelines/classified_analysis.py           # attach_special_clause_reviews (Step 4)
ai/tests/special_clauses/                     # 계약·매칭 테스트
ai/tests/pipelines/test_classified_analysis.py# Step 4 테스트
data/rules/
  special_clause_catalog.json                # #1 카탈로그(초안)
  special_clause_evidence_map.csv            # #2 근거 범위(초안)
  source_inventory.csv                       # RAG 출처 대장
data/evaluation/special-clauses/             # #3 블라인드 평가셋(draft)
data/rag/sources/SRC-CIVIL-LEASE.txt         # 민법 발췌(536·615·623·626·654)
docs/data/special-clause-review-guide.md     # 사람 검토 방법
docs/planning/special-clause-evidence-rag-implementation-plan.md  # 플랜
```

## 9. 검증 명령
```
# AI 전체
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 <env>/python.exe -m pytest ai -q
# 특약 관련만
... -m pytest ai/tests/special_clauses ai/tests/pipelines/test_classified_analysis.py ai/tests/schemas ai/tests/rag/test_source_manifest.py -q
# Backend 회귀
cd backend; ... -m pytest tests/api/test_case001_e2e.py tests/api/test_analyses.py -q
```
