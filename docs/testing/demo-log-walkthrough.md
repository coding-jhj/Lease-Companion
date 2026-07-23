# 데모 로그 해설 가이드 (스크럼 전 파이프라인 점검용)

목적: 데모 중 CLI 로그를 화면에 띄우고 각 줄이 어떤 파이프라인 단계인지 즉시 설명한다.
기준 흐름은 루트 `AGENTS.md`의 데이터 흐름 5블록이다.

## 준비

```powershell
conda activate lease
.\scripts\start-dev.ps1 -Force
```

- 한 터미널에 `[BE]`(백엔드)·`[FE]`(Vite) 로그가 태그로 병합 출력된다.
- 브라우저는 옆 창. 조작 → 로그 → 화면 순서로 말한다.
- 로그 레벨은 `backend/app/main.py`의 `logging.basicConfig(level=INFO)` 기준.
- 같은 파일에서 `httpx`·`httpcore`·`google_genai`를 WARNING으로 낮춰 둔다. 그래서
  `AFC is enabled`, httpx 요청 URL 줄은 더 이상 보이지 않는다. 같은 정보를 `GeminiGateway`가
  `task`·`model`·`attempt`·`latency_ms`로 더 정확히 남기기 때문이다.

## 읽는 법 (핵심)

- `[1/4]`~`[4/4]` 번호가 곧 해설 순서다. 이 4줄만 따라가면 파이프라인 전체가 설명된다.
- **INFO는 진행, WARNING·ERROR는 조용히 흡수된 실패다.** 이 서비스는 장애를 사용자에게
  안 보이게 흡수하므로, 화면이 멀쩡해도 WARNING이 떠 있으면 무언가 폴백된 것이다.
- 한 분석 실행의 로그는 `analysis_run_id`로 묶어 추적한다.

## 화면 조작 → 로그 대응표

| # | 사용자 조작 | 나오는 로그 | 설명 문장 |
|---|---|---|---|
| 1 | 문서 업로드 | `POST /api/.../documents 201` (uvicorn 액세스) | "업로드는 문서 처리 API가 받고 문서 저장소에 저장합니다." |
| 2 | 추출 실행 | `[1/4] 문서 추출 시작 (extraction_run_id=...)` | "PDF 텍스트 추출 단계 진입. 디지털 PDF는 PyMuPDF, 스캔본은 Gemini VLM 1회 호출." |
| 3 | (Gemini 호출 시) | `Gemini 호출 성공 task=document_extraction model=... attempt=1 latency_ms=...` | "스캔본이라 VLM이 OCR과 구조화를 함께 합니다. 별도 OCR 단계가 없습니다." |
| 4 | 추출 완료 | `[1/4] 문서 추출 종료 (... status=completed 계약서=판독12/28 등기=판독6/10)` | "판독 성공 필드 수입니다. **값은 로그에 안 찍습니다** — 개인정보 원칙. 다음은 사용자 확인·수정 화면입니다." |
| 5 | 추출값 확인·수정 후 분석 시작 | `[2/4] 구조화·규칙 판정 시작 (analysis_run_id=...)` | "사용자가 확정한 입력 스냅샷으로 분석 1회를 실행합니다." |
| 6 | (Gemini 호출 시) | `Gemini 호출 성공 task=clause_classification ...` | "상용 LLM은 조항 구조화만 합니다. 판정은 안 합니다." |
| 7 | 라우팅 | `라우팅 정상 stage=embedding selected=gemini_embedding_001` | "단계별로 어떤 경로를 골랐는지 남깁니다. 실패하면 이 줄이 WARNING으로 바뀝니다." |
| 8 | 규칙 완료 | `[3/4] 규칙 판정 완료 (... R=24 J=12 특약근거=n 즉시확인=n 상태=미기재:8,불일치:2 근거있음=20/24)` | "여기가 최종 판정입니다. Python 규칙 엔진이 R01~R24를 결정론으로 냅니다. 상태 분포와 공식 근거가 붙은 항목 수까지 보입니다." |
| 9 | 생성 완료 | `[4/4] 안내 생성 완료 (... provider=gemini 규칙안내=n 특약안내=n 템플릿폴백=n 사유=...)` | "판정은 그대로 두고 쉬운 설명·질문·행동만 생성합니다. `템플릿폴백=0`이면 전부 LLM 생성입니다." |
| 10 | 리포트 화면 | 추가 로그 없음 | "결과는 분석 결과·이력 DB에서 조회만 합니다." |

## 실패·폴백 로그 (나오면 오히려 설명 포인트)

INFO 줄 사이에 WARNING·ERROR가 섞이면 **그게 설명할 지점**이다.

| 로그 | 수준 | 설명 문장 |
|---|---|---|
| `Gemini 호출 재시도 task=... status=503 wait_ms=...` | WARNING | "Gateway가 재시도를 제어합니다. 503·timeout만 지수 백오프로 1회 재시도합니다." |
| `Gemini 일일 할당량 소진 task=... — 재시도하지 않음` | ERROR | "무료 티어의 모델별 하루 한도입니다. 재시도하지 않고 즉시 중단해 할당량을 더 태우지 않습니다." |
| `Gemini 호출 실패(재시도 불가) task=... status=400` | ERROR | "요청 자체가 거부된 경우입니다. 재시도해도 같으므로 바로 폴백으로 넘깁니다." |
| `Gemini 호출 최종 실패 task=... attempts=2` | ERROR | "재시도까지 소진된 경우입니다. 이후 단계가 안전 폴백을 씁니다." |
| `Gemini 대기 예산 초과로 중단 task=... budget_ms=3000` | ERROR | "연습 답변처럼 실시간성이 중요한 단계는 총 대기시간을 제한합니다. 사용자를 기다리게 하지 않습니다." |
| `라우팅 fallback stage=embedding primary=...→selected=bm25 reason=quota_exceeded` | WARNING | "임베딩 한도가 막혀 BM25 단독 검색으로 대체했습니다. 판정은 바뀌지 않습니다." |
| `[1/4] 추출 실패 사유 (...)` | WARNING | "추출 실패를 상태로 남겨 무한 폴링을 막습니다." |
| `[2/4] 조항 구조화 fallback (method=safe_fallback 후보=0) — 특약 근거·안내가 비게 됩니다` | WARNING | "LLM 구조화가 실패해 후보가 0입니다. 규칙 엔진은 명세대로 `확인 필요`·`확인 불가`를 냅니다." |
| `[3/4] 공식 근거 0건 — RAG 검색 실패 또는 임베딩 한도 소진` | WARNING | "근거가 없으면 생성 단계가 전량 템플릿 폴백이 됩니다. 다음 `[4/4]` 줄이 그걸 확인해 줍니다." |
| `[4/4] 규칙 안내 전량 템플릿 폴백 (사유=missing_evidence:18)` | WARNING | "LLM 생성이 하나도 반영되지 않았습니다. 사유별 개수까지 나오므로 원인을 바로 짚습니다." |
| `generation_guardrail_blocked` | WARNING | "guardrail이 단정 표현·근거 없는 문장을 차단하고 템플릿 폴백으로 대체했습니다." |
| `generation_pii_gate_blocked` | WARNING | "개인정보가 그대로 남은 생성 결과를 차단한 것입니다." |
| `special_clause_retrieval_provider_failed` | WARNING | "RAG 검색 실패. 근거는 빈 목록으로 두고 판정은 바꾸지 않습니다." |
| `연습 복기 공식 근거 검색에 실패해...` | WARNING | "계약 연습 복기의 근거 검색 실패. 사용자 오답으로 기록하지 않습니다." |
| `분석 실행 실패 (analysis_run_id=...)` + traceback | ERROR | "예외 위치까지 남깁니다. 실패는 status=failed로 저장해 무한 폴링을 막습니다." |

### 실패 연쇄를 읽는 예시

2026-07-23 실제 실행에서 나온 흐름이다. 인과가 로그만으로 읽힌다.

```
[2/4] 구조화·규칙 판정 시작 (analysis_run_id=1105d6ee...)
ERROR   Gemini 호출 실패(재시도 불가) task=clause_classification status=400
WARNING [2/4] 조항 구조화 fallback (method=safe_fallback 후보=0) — 특약 근거·안내가 비게 됩니다
WARNING 라우팅 fallback stage=embedding primary=gemini_embedding_001→selected=bm25 reason=quota_exceeded
[3/4] 규칙 판정 완료 (R=24 J=12 특약근거=0 즉시확인=5 근거있음=0/24)
WARNING [3/4] 공식 근거 0건 — RAG 검색 실패 또는 임베딩 한도 소진
[4/4] 안내 생성 완료 (템플릿폴백=18 사유=missing_evidence:18)
WARNING [4/4] 규칙 안내 전량 템플릿 폴백 — LLM 생성 결과가 하나도 반영되지 않았습니다
```

설명 문장: "임베딩 한도가 막혀 공식 근거를 못 붙였고, 근거가 없으니 생성 단계가 전부 템플릿으로
떨어졌습니다. **판정 24건은 그대로 나갔습니다** — 규칙 엔진은 LLM에 의존하지 않기 때문입니다."

## 미리 준비할 3문장 (질문 대비)

1. "판정은 LLM이 아니라 Python 규칙 엔진이 냅니다. 로그의 `[3/4]` 줄이 최종 판정 지점입니다."
2. "LLM 실패는 사용자에게 오류로 안 나갑니다. 템플릿 폴백 개수와 **사유**가 `[4/4]`에 찍힙니다."
3. "로그에 계약 내용·개인정보는 남기지 않습니다. id·건수·상태만 찍습니다."

## 429가 데모 중에 터졌을 때 (2026-07-23 기준 현실적 시나리오)

무료 티어 한도는 **모델별 하루 단위**(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`)라
데모 도중 소진될 수 있다. 당황하지 말고 아래 순서로 말한다.

1. "지금 뜬 429는 무료 티어 하루 한도입니다. 서비스 장애가 아닙니다."
2. "Gateway가 재시도하지 않고 즉시 중단합니다. 할당량을 더 태우지 않는 설계입니다."
3. "판정은 영향받지 않습니다. `[3/4]` 줄의 규칙 판정은 Python 규칙 엔진이 결정론으로 냅니다."
4. "쉬운 설명·질문·체크리스트만 템플릿 폴백으로 나갑니다. `[4/4]`의 `템플릿폴백=n 사유=...`가 그 근거입니다."
5. 화면을 그대로 보여준다 — 리포트가 비지 않는 것 자체가 폴백 설계의 증명이다.

즉, **429는 데모 실패가 아니라 장애 흡수 설계를 보여주는 장면**으로 전환한다.

## 주의

- 2026-07-23 현재 `.env`에 모델 임시 오버라이드가 있어 로그의 `model=`은 확정 모델(`gemini-3.5-flash`)이
  아니라 `gemini-3-flash-preview`·`gemini-3.1-flash-lite`로 찍힌다. 3.5 Flash 한도가 리셋되면
  `.env`의 `GEMINI_MODEL_*` 오버라이드 줄을 제거한다. 물어보면 "무료 한도 소진 우회이며 확정 모델은 3.5 Flash"로 답한다.
- 프론트 개발 서버는 `<StrictMode>` 때문에 같은 GET이 2번씩 찍힌다(`main.tsx`). React가 개발 모드에서
  `useEffect`를 의도적으로 두 번 실행하는 것이고, 프로덕션 빌드에서는 1회다. 물어보면 그렇게 답한다.
- `GET /extractions/latest` 반복은 분석 진행 상태 폴링이다. 버그가 아니다.
- 데모 직전 리허설을 여러 번 돌리면 그만큼 한도를 쓴다. 리허설은 1회로 끝낸다.
