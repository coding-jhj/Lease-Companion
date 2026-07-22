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

## 2. 혼자 작업용 0~11 계획 현재 상태
최신 작업 3 검증: **AI 687(2 skipped)** 통과. 직전 전체 통합 기준은 **AI·Backend 758(2 skipped) · Frontend 101** 통과.

| 작업 | 상태 | 산출물·남은 범위 |
|------|------|------------------|
| 작업 0 — 기준선 | ✅ 완료 | `main`에서 기준 테스트·사용자 미커밋 파일 분리 기록 |
| 작업 1 — 공식 근거표 | ✅ 완료 | 근거 경계 수정, 커밋 `00692a5` |
| 작업 2 — 평가셋 잠금 | ✅ 완료 | 6유형×5범주, 검색·생성 6유형+근거 없음, SHA256 잠금 |
| 작업 3 — R/J 경계 ADR | ✅ 완료 | `docs/decisions/2026-07-22-special-clause-rule-judgment-boundary.md` |
| 작업 4 — 규칙 연결 보완 | ⚠ 기반 구현 완료 | 6유형 매칭·R/J 연결은 완료, 계획의 추가 문장·상충 비교 보완은 남음 |
| 작업 5~10 | ❌ 미착수 | 아래 5절 |
| 작업 11 | ⏸ 의도적으로 보류 | 독립 검토·실제 Gemini/Cohere·운영 활성화 |

`feat/lmk`에서 선행 구현된 canonical 스키마와 결정론적 매칭 기반은 작업 4 이후에 다시 만들지 않고 재사용한다.

---

## 3. "부족 자료 4가지" 상태
Codex가 지적한 4가지 부족 자료 — **전부 초안 완료**, 단 검토·수정 필요.

| # | 자료 | 파일 | 상태 |
|---|------|------|------|
| 1 | 특약 카탈로그 정답 정의 | `data/rules/special_clause_catalog.json` | 게이트 A 반영·R/J 연결 계약 확정 ✅ / **독립 재확인 전 unverified 유지** |
| 2 | 유형별 공식 근거 조·항 범위 | `data/rules/special_clause_evidence_map.csv` | 게이트 A 반영 ✅ / **독립 재확인 전 unverified 유지** |
| 3 | 블라인드 평가셋 | `data/evaluation/special-clauses/*.jsonl` | 6유형×5범주·검색/생성 근거 없음 사례·SHA256 잠금 ✅ / **게이트 B(독립 검토) 미완** |
| 4 | canonical 스키마 | `unified.py` | ✅ 완료(수정 불필요) |

민법 코퍼스 공백도 해소: `data/rag/sources/SRC-CIVIL-LEASE.txt`에 제536·615·623·626·654조 발췌(형식·manifest 정합 검증 완료).

---

## 4. 게이트 A(법률 검토) 결과
담당자가 원문 대조 검토를 완료함. **핵심 문제: "문구가 명확한가"(명확성)와 "그 조건이 임차인에게 불리한가"(불리조건 탐지)가 R08·R09·R18에서 섞여 있음.** 명확하게 불리한 특약이 오히려 "명확=정상"으로 처리될 수 있음.

### 4-1. R/J 책임 경계 — 작업 3 확정

상세 결정: [`2026-07-22-special-clause-rule-judgment-boundary.md`](../decisions/2026-07-22-special-clause-rule-judgment-boundary.md)

1. **R08 유지**: 반환 시점·조건 명확성이라는 기존 의미를 유지한다. 미래 사건 연동의 최종 확인 신호는 J10과 `SpecialClauseReview`에서 처리한다.
2. **R09 유지**: 수리·원상복구 책임 명확성이라는 기존 의미를 유지한다. `SC-REPAIR-SCOPE`와 `SC-RESTORATION-SCOPE`로 논점만 구분하고 신규 canonical 필드는 추가하지 않는다.
3. **R10·R19 분리**: R10은 제한 특약 문구 유무, R19는 계약·잔금·입주 시점별 실제 등기 권리변동 확인이다. 실제 자료가 없으면 R19를 자동 완료하지 않는다.
4. **J12 유지**: 본문·특약 상충의 최종 판정은 J12가 담당한다. 신규 R25는 추가하지 않는다.
5. 카탈로그는 R/J 참조와 검색 범위만 제공하며 `status`·`urgency`·최종 `reason`을 만들지 않는다.

### 4-2. evidence_map 수정 — 2026-07-22 반영 완료
| 유형 | 반영할 것 |
|------|-----------|
| DEFERRED-REFUND | **민법 제536조(동시이행) 직접 근거 추가**, 주임법 제4조는 **제2항(보호 규정)으로 정정·보조 근거화**, 제10조는 조건부로 강등, 동시이행 대법원 판례는 reference_cases로 |
| REPAIR-SCOPE | **민법 제626조 추가**, 표준계약서 **제4조 제2~4항** 추가, "주요설비=무조건 임대인" 대신 "사용·수익에 필요한 설비의 노후·불량 수리 포괄 전가" 탐지로 |
| RESTORATION-SCOPE | **제10조 제거**, 표준계약서 제9조 단서(통상손모·노후 제외)를 핵심 근거로 유지, 민법 615·654 유지 |
| RIGHTS-CHANGE | 제3조·제3조의2는 "위험 발생 이유"로, **표준계약서 특약사항(SRC-STD-LEASE 49~50행)·안심체크리스트(SRC-MOLIT-CHECKLIST 43·46·58행)를 "권장 확인·특약 근거"로 명시** |
| MANAGEMENT-FEE | 지금 근거로는 "임의 변경"보다 **"관리비·추가비용 명확성"**이 정확. 유형명 정리(`SC-MANAGEMENT-FEE-CLARITY`) 또는 변경권한 필드 추가. 확인·설명서 관리비 항목(SRC-CONFIRM-FORM 25~31행) 유지 |
| MAIN-SPECIAL-CONFLICT | "본문 전반" 대신 **상충 주제별 동적 근거 연결**(보증금→표준9조·민법536 / 수리→표준3·4조·민법623 / 원상복구→표준9조·민법615·654 / 관리비→표준1조·확인설명서 / 임대차기간→표준2조·주임법4 / 권리변동→표준특약·주임법3·3의2) |

### 4-3. 주임법 제10조(강행규정) 조건부화 — 2026-07-22 반영 완료
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

## 5. 남은 작업
| 작업 | 내용 | 의존 |
|------|------|------|
| 작업 3 | R08·R09·R10·R19와 J10·J11·J12 책임 경계 ADR | ✅ 완료 |
| 작업 4 | 기존 결정론적 매칭·R/J 연결의 문장 범위와 상충 비교 보완 | 작업 3 |
| 작업 5 | 특약 원문 기반 RAG 검색·재정렬(`rag/clause_service.py`), 조·항 단위 청킹 보강 | 작업 4 |
| 작업 6 | 근거 기반 특약 설명·질문·수정요청 생성 + guardrail | 작업 5 |
| 작업 7 | 파이프라인 종단(catalog→R/J→clause RAG→generation→guardrail) + 전용 fixture | 작업 5·6 |
| 작업 8 | Backend 저장·API(`special_clause_reviews`/`special_clause_items` 응답) | 작업 7 |
| 작업 9 | Frontend `확인이 필요한 특약` 섹션과 PDF | 작업 8 |
| 작업 10 | API 키 없는 오프라인 종단 검증·문서 | 작업 4~9 |
| 작업 11 | 독립 검토·실제 provider 검증·운영 활성화 | 작업 10 이후 별도 진행 |

### chroma 재인덱싱
민법 등 새 출처가 실제 검색되려면 인덱스 재빌드가 필요하다. API 키 없는 BM25·고정 embedding fixture는 작업 5에서 처리하고, 실제 embedding 호출은 작업 11로 미룬다.

---

## 6. 다음 담당자 착수 우선순위 (권장)
1. [완료] **작업 2 평가셋 잠금** — 6유형×5범주와 검색·생성 사례를 잠갔고 `draft_pending_human_review`를 유지한다.
2. [완료] **작업 3 R/J 경계 ADR** — 기존 R/J 식별자를 유지하고 R10·R19 역할, J10·J11·J12 최종 판정 책임을 고정했다.
3. 다음은 작업 4 규칙 보완이다. 이후 5 RAG → 6 생성·guardrail → 7 AI 종단 → 8 Backend → 9 Frontend → 10 오프라인 종단 검증 순서로 구현한다.

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
