# J13 임차권 보호 제한 특약 판정 설계

- 날짜: 2026-07-23
- 상태: 설계 승인
- 배경 결정: 팀 회의에서 `AGENTS.md`를 개정해 J13 이후로 판정 축을 확장하기로 함

## 목적

임차인의 법정 보호 장치를 특약으로 제한하는 조항을 판정 축에 올린다. 현재 이런 특약은
연결할 R/J가 없어 특약 카드가 만들어지지 않고, 화면에 아무것도 표시되지 않는다.

2026-07-23 실측: 실제 계약서(contract_id=76)의 확인 특약 6건이 전부 카탈로그 미매칭이었고
`special_clause_reviews`가 0건이었다. 카탈로그 6종이 독소조항만 담고 있어 생긴 공백이다.

## 범위

이 설계가 다루는 유형은 5개다.

1. 전입신고·확정일자 제한
2. 계약갱신요구권 포기
3. 임대인 변경 시 승계 배제
4. 전세권·임차권등기 금지
5. 보증보험 협조 배제

다루지 않는 것: 중도해지 위약금(R25 별건), 잔금 전 선입주(J08 재사용), 전대 금지(민법
제629조가 RAG 코퍼스에 없음), 반려동물 금지(제외 확정).

## 결정 사항

### 1. 판정은 J13 하나로 통합한다

5개 유형을 각각의 판정으로 나누지 않는다.

근거:
- J축은 매 분석마다 전부 반환해야 한다(일부만 반환하는 중간 상태 불허). 5개로 나누면
  특약이 없는 대다수 계약서에서 `적용 제외` 5줄이 리포트 상단을 채운다.
- 유형별 원문·근거·행동은 `SpecialClauseReview` 카드가 이미 유형별로 구분해 보여준다.
  판정 개수를 늘려야 얻는 정보가 없다.
- 5개 유형의 성격("보호 장치를 특약으로 제한")과 행동("해당 문구 삭제 요청")이 같다.
- 문서·골드셋·프론트 파급이 12→13으로 끝난다.

`status`·`urgency`만 단일이고 `reason`·`recommended_actions`·`evidence_sources`는
유형 수만큼 담는다.

### 2. C영역(책임·특약)에 넣는다

E영역을 신설하지 않는다. J10~J12와 J13이 모두 특약 원문을 입력으로 쓰므로 묶이는 근거가
있고, `AGENTS.md`는 "4영역 12항목" → "4영역 13항목" 한 줄만 고치면 된다.

### 3. 허용 상태는 3개로 제한한다

`확인 필요` / `적용 제외` / `확인 불가`.

`상충 가능`은 쓰지 않는다. 강행규정 위반 여부를 표현하게 되어 "AI는 적법·위법을 확정하지
않는다"는 원칙에 닿고, J12가 `본문-특약 상충`에 같은 상태를 써서 의미가 섞인다.

`명확`/`불명확` 축도 쓰지 않는다. J13은 "내용이 명확한가"가 아니라 "제한 특약이 있는가"다.

`triggers_actions`는 `ACTION_TRIGGER_STATUSES`(`unified.py:428`)에서 자동 파생되며
`적용 제외`만 false다.

### 4. J12와 독립 판정한다

같은 특약이 J12와 J13에 동시에 걸릴 수 있고 그것이 정상이다.

- J12: 본문과 특약이 서로 어긋나는가
- J13: 특약이 임차인의 법정 보호 장치를 제한하는가

관점이 다르므로 배타 처리하지 않는다. R·J 다축 원칙과 일치한다. 중복 안내 문구는
프론트의 기존 행동 허브 중복 제거가 처리한다.

### 5. 탐지는 카탈로그를 단일 출처로 한다

`data/rules/special_clause_catalog.json`에 유형별 항목을 추가하고, J13 규칙이
`match_special_clauses()` 결과를 읽어 판정한다.

검토한 대안:
- **규칙 전용 정규식**: 같은 패턴이 카탈로그와 규칙 두 곳에 중복되어 "판정은 걸렸는데
  카드가 없다"는 어긋남이 생긴다.
- **classification 후보 활용**: LLM 실패 시 후보가 0이 되어 판정이 흔들린다.
  규칙 엔진은 결정론이어야 한다(`AGENTS.md`).

`special_clauses` 모듈은 `catalog`·`models`만 import하므로 `rules`에서 호출해도 순환
의존이 없다(확인 완료).

## 판정 정의

| 항목 | 값 |
|---|---|
| ID | `J13` |
| 이름 | 임차권 보호 제한 특약 |
| 영역 | C (책임·특약) |
| 입력 | `special_clauses`, `special_clauses_present` |
| 허용 상태 | `확인 필요` / `적용 제외` / `확인 불가` |
| 기본 시급도 | `즉시 확인` |

판정 로직:

```
특약 필드 추출 실패·판독 불가                      → 확인 불가
확인된 특약 원문이 없음                            → 적용 제외
특약은 있으나 J13 연결 카탈로그 항목 매칭 0건       → 적용 제외
J13 연결 카탈로그 항목 1건 이상 매칭               → 확인 필요
```

판정 대상은 **`special_clauses`의 확인된 원문 목록**이다. `special_clauses_present`는
보조 신호로만 쓴다. 둘이 어긋나면(예: `present=true`인데 목록이 비어 있음) `확인 불가`로
처리한다.

매칭 대상은 **`related_judgment_ids`에 `J13`이 있는 카탈로그 항목만**이다. 기존
독소조항 6종(`SC-DEFERRED-REFUND` 등)이 매칭돼도 J13에는 영향을 주지 않는다. 그쪽은
각자 연결된 R08·R09·R10·R18·J09~J12가 담당한다.

`확인 필요`일 때 `reason`에 걸린 유형과 건수를, `recommended_actions`에 유형별 행동을,
`evidence_sources`에 유형별 조문을 담는다.

법적 효력은 단정하지 않는다. "무효"·"위법" 대신 "해당 문구 삭제를 요청하고 공인중개사에게
확인하세요" 수준으로만 안내하며, 카탈로그의 `prohibited_terms`가 guardrail에서 강제한다.

## 카탈로그 항목

전부 `related_judgment_ids: ["J13"]`, `related_rule_ids: []`.

`related_rule_ids`를 비우는 이유: `_build_special_clause_reviews`가 J를 우선 사용하므로
J13이 항상 존재하는 한 R 링크는 쓰이지 않는다. 검증 대상만 늘어난다.

| catalog_id | 유형 | 근거 조문 (RAG 코퍼스 확인됨) |
|---|---|---|
| `SC-MOVEIN-REPORT-BAN` | 전입신고·확정일자 제한 | 주택임대차보호법 제3조(대항력 등), 제3조의2(보증금의 회수), 제3조의6(확정일자 부여 및 임대차 정보제공 등), 제10조(강행규정) |
| `SC-RENEWAL-WAIVER` | 계약갱신요구권 포기 | 주택임대차보호법 제6조(계약의 갱신), 제6조의3(계약갱신 요구 등), 제10조 / 표준계약서 제8조(갱신요구와 거절) |
| `SC-SUCCESSION-EXCLUSION` | 임대인 변경 시 승계 배제 | 주택임대차보호법 제3조(대항력 등), 제10조 |
| `SC-REGISTRATION-BAN` | 전세권·임차권등기 금지 | 주택임대차보호법 제3조의3(임차권등기명령), 제3조의4(「민법」에 따른 주택임대차등기의 효력 등), 제10조 |
| `SC-GUARANTEE-REFUSAL` | 보증보험 협조 배제 | 주택임대차보호법 제3조의7(임대인의 정보 제시 의무), SRC-HUG(전세보증금반환보증 상품개요) |

각 항목은 기존 6종과 동일한 구조를 따른다: `include_patterns`, `exclude_patterns`,
`allowed_source_sections`, `legal_effect_review`, `explanation_boundary.prohibited_terms`.

`legal_effect_review`는 법률 검토 전이므로 기존 6종과 동일하게
`hta_article_10_applicable: "undetermined"`, `court_or_expert_review_needed: true`로 둔다.

### 패턴 정확도의 한계

실제 계약서 문구 샘플이 없는 상태에서 작성하는 초안이다. 2026-07-23 실측에서 기존
카탈로그 6종이 실제 특약 6건을 하나도 잡지 못한 것이 같은 원인이다.

따라서 초기 패턴은 **명백한 표현만 보수적으로** 잡는다. 미탐은 허용하고 오탐을 최소화한다.
멀쩡한 특약을 위험으로 표시하는 쪽이 더 나쁘기 때문이다.

문구 샘플이 확보되면 패턴을 넓히고 `catalog_test.jsonl`로 매칭률을 측정한다. 그 전까지
카탈로그는 `review_status: unverified`를 유지한다.

## 스키마 하위호환

### 허용 시퀀스를 2개로

```python
allowed_judgment_sequences = (
    [f"J{index:02d}" for index in range(1, 13)],  # 레거시: 영구 허용
    list(JUDGMENT_IDS),                            # 현행: 상수 기반
)
```

레거시 J01~J12를 영구히 허용한다. DB에 저장된 과거 `AnalysisRun.result`가 계속 읽힌다.
이후 J14 이상이 추가돼도 `JUDGMENT_IDS`만 늘리면 되고 이 코드는 다시 고치지 않는다.

이 변경을 빠뜨리면 과거 분석 결과 전량이 `ValidationError`로 읽히지 않는다. 리포트
재조회·체크리스트·이력이 모두 깨지는 데이터 손실급 사고다.

### 하드코딩 제거

| 위치 | 현재 | 변경 |
|---|---|---|
| `unified.py:130` `JUDGMENT_IDS` | `range(1, 13)` | `range(1, 14)` |
| `unified.py:1143` `_JudgmentId` | `^J(?:0[1-9]\|1[0-2])$` | `JUDGMENT_IDS`에서 생성 |
| `unified.py:1233` `JudgmentResult.judgment_id` | 같은 정규식 | 같은 방식 |
| `unified.py:933` `JudgmentInput.judgment_ids` | `max_length=12` | `len(JUDGMENT_IDS)` |
| `unified.py:1280` `AnalysisRunResult.judgments` | `max_length=12` | `len(JUDGMENT_IDS)` |
| `unified.py:788` 오류 메시지 | `"J01~J12 canonical 순서"` | 일반 문구 |

정규식을 상수에서 생성하면 두 곳이 어긋날 여지가 사라진다.

### 추가 테이블 항목

- `DEFAULT_JUDGMENT_URGENCY["J13"] = Urgency.IMMEDIATE`
- `JUDGMENT_INPUT_SPECS["J13"]` — 입력은 `special_clauses`, `special_clauses_present`.
  J12와 동일하므로 **추출 스키마·프롬프트·사용자 확인 화면 변경이 없다.**
- `ALLOWED_JUDGMENT_STATUSES["J13"] = {CHECK_NEEDED, NOT_APPLICABLE, CANNOT_CHECK}`

## 테스트 전략

TDD로 진행하며 빨간불을 두 번 확인한다.

```
1. RED   J13 포함 시퀀스가 AnalysisRunResult에 들어간다   → 실패 (J13 미존재·정규식 거부)
2. GREEN JUDGMENT_IDS·정규식·max_length·J13 규칙 구현      → 통과
3. RED   레거시 J01~J12 결과가 여전히 읽힌다               → 실패 (허용 시퀀스가 하나뿐)
4. GREEN allowed_judgment_sequences 도입                   → 둘 다 통과
```

3번이 하위호환 사고를 재현하는 테스트다. 실제로 빨간불을 봐야 shim이 검증된다.

추가 테스트:
- J13 판정 로직 4분기(확인 불가 / 적용 제외 2종 / 확인 필요)
- 카탈로그 5개 항목이 J13에 연결되고 카드 status가 J13과 일치
- 같은 특약이 J12·J13에 동시에 걸려도 검증을 통과

## 영향 범위

| 구분 | 파일 |
|---|---|
| AI 스키마 | `schemas/unified.py` |
| AI 규칙 | `rules/judgments.py` |
| AI 카탈로그 | `data/rules/special_clause_catalog.json` |
| RAG 근거 매핑 | `data/rules/special_clause_evidence_map.csv` |
| 판정 명세 데이터 | `data/rules/judgment_spec.csv` |
| 픽스처·골드셋 | `data/sample/fixtures/case-001/analysis_run_result.json`, `data/sample/expected-results/judgment_goldset.jsonl` |
| 생성 스키마 | `data/schemas/generated/*.json` (Pydantic에서 재생성, 손으로 쓰지 않음) |
| Backend | `app/schemas/checklist.py` |
| Frontend | `features/judgment-results/plainGuides.ts`, `types/api.ts` |
| 문서 | `AGENTS.md`("4영역 12항목"→"13항목"), `docs/data/judgment-spec.md`, `docs/api/data-contract-v1.md` |

RAG 근거 매핑을 빠뜨리면 `generation/service.py:738`의 `missing_evidence` 경로로 빠져
J13 안내가 전량 템플릿 폴백이 된다. 2026-07-23 실행에서 실제로 관측된 경로다.

## 화면 신호등

영향 없다. 신호등 3단계는 `urgency`에서 파생되므로 판정 개수와 무관하다.

## 후속

- 실제 계약서 특약 문구 샘플 확보 후 패턴 확장·매칭률 측정
- 법률 검토 후 `legal_effect_review`·`review_status` 갱신
- 민법 제629조 코퍼스 추가 후 전대 금지 유형 검토
- `catalog.py`가 `review_status`를 확인하지 않고 무조건 로드하는 문제(별건)
