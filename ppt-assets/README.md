# PPT 2·3번 자료 묶음

측정일: 2026-07-28
모델: 확정 운영 모델 `gemini-3.5-flash` (유료키 기준, `.env` 임시 오버라이드 해제 후 측정)

## 2. 평가 리포트

- `02-evaluation-summary.svg` / `.png`: PPT 삽입용 핵심 지표 그래프
- `02-evaluation-summary.csv`: 표 편집용 원본
- 운영 경로 실측(Gemini 3.5 Flash · Cohere rerank): 필드 추출 `96.67%`,
  R01–R10 규칙 상태 `97.00%`, 시급도 `100%`, 특약 RAG source `91.67%`,
  source+section `77.78%`
- Online RAGAS 3건: Faithfulness `72.22%`, Answer Relevancy `82.47%`
- 로컬 회귀 기준선(외부 호출 0): 추출·R·J `100%`, 특약 RAG `91.67%` / `66.67%`

그래프는 측정 성격에 따라 4개 그룹으로 나눠 표기한다.

| 그룹 | 항목 | 뜻 |
|---|---|---|
| 운영 경로 실측(초록) | 추출 96.67% · 규칙 97% · 시급도 100% · 특약 RAG 91.67%/77.78% | 실제 서비스 경로. 발표용 성능 수치 |
| 품질 측정(초록) | Faithfulness 72.22% · Relevancy 82.47% | judge 기반. 대상 답변은 고정 QA |
| 로컬 회귀 기준선(파랑) | 추출·R·J 100% · 특약 RAG 91.67%/66.67% | 정규식·BM25 폴백. 회귀 감지용 |
| 해석 주의(회색) | End-to-End 무오류 실행 · 일반 RAG 정답 출처 recall | 구조적으로 100%가 나오는 값 |

해석 시 주의:

- 측정 중 PII 처리 버그 2건을 발견해 수정했다(아래 수치는 수정 후 값).
  ① ISO 날짜를 계좌번호로 오탐 → `issue_date` 0/10, 시급도 62.96%.
  ② 대괄호 없는 토큰(`PERSON_1`) 복원 실패 → `owner_names` 0/10.
  수정 후 두 필드 모두 10/10, 시급도 100%. 회귀 테스트 3건 추가.
- 규칙 엔진은 결정론이다. 규칙 정확도 `100%`(정규식 입력) → `97%`
  (Gemini 입력) 차이는 엔진이 아니라 추출 오류가 전파된 결과다.
- 남은 추출 오류는 등기 tri-state 플래그와 금액에 몰려 있다.
  `seizure_present` 7/10, `trust_present` 8/10, `balance_payment` 9/10,
  `contract_payment` 9/10, `provisional_seizure_present` 9/10.
- J01–J13은 사용자 확인 완료 입력 기준이라 추출 오류가 전파되지 않는다.
- `End-to-End 무오류 실행`은 정확도가 아니다. 케이스가 하나라도 실패하면
  평가 자체가 중단되므로 100% 미만이 나올 수 없다.
- `일반 RAG`의 context precision은 지표에서 뺐다. 검색이 허용 출처
  화이트리스트(=정답 출처) 안에서만 이뤄져 항상 1.0이 된다. 남는 의미인
  recall만 표기하며, 코퍼스는 6출처·37청크다.
- Online RAGAS의 평가 대상 답변은 파이프라인 생성 결과가 아니라
  `data/evaluation/ragas_llm_test.jsonl`에 손으로 써둔 고정 QA 3건이다.
  실제 모델이 관여하는 건 judge뿐이다.
- 채점 로직은 변이 테스트로 확인했다. 보증금·종료일·예금주·특약을 변조하면
  추출 16/16 → 15/16, 등기 소유자 변조 시 규칙 100/100 → 99/100,
  J01 기대 상태 변조 시 판정 51/51 → 50/51로 떨어진다.

재측정 명령:

```powershell
python scripts/evaluate_extraction_gemini.py `
  --metrics-jsonl outputs/provider-metrics/extraction-gemini-<날짜>.jsonl
python scripts/evaluate_retrieval_providers.py `
  --metrics-jsonl outputs/provider-metrics/retrieval-provider-<날짜>.jsonl
```

## 3. 응답 엔진 호출 로그 요약

- `03-mode-cycle-cost.svg` / `.png`: 실제 계약 점검과 3턴 시뮬레이션 비교
- `03-mode-cycle-summary.csv`: 모드별 사용량·비용·시간
- `03-actual-engine-summary.csv`: 실제 계약 점검 엔진별 집계
- `03-simulation-engine-summary.csv`: 시뮬레이션 엔진별 집계
- `03-gemini-3.5-ttfb.svg` / `.png`: Gemini 3.5 Flash 스트리밍 TTFB 10회 개별값
  (최소 11,093 · 중앙값 13,632 · 평균 13,761 · 최대 16,093 ms)

실측 기준:

| 모드 | 표본 | 호출 | 알려진 비용 | 원화 단순 환산 | 1콜 평균 |
|---|---:|---:|---:|---:|---:|
| 실제 계약 점검 | 1사이클 | 79 | $0.1032675 | 약 151.80원 | $0.0013072 |
| 시뮬레이션 | 3턴 1사이클 | 6 | $0.014766 | 약 21.71원 | $0.0024610 |

원본 로그:

- 실제 계약 점검: `outputs/provider-metrics/actual-contract-cycle-2026-07-28-paid35.jsonl`
  (2026-07-28 재측정. 조항 분류가 provider로 성공한 완전 사이클)
- 시뮬레이션: `outputs/provider-metrics/simulation-cycle-2026-07-28.jsonl`
- TTFB: `outputs/provider-metrics/gemini-3.5-flash-ttfb-2026-07-28.jsonl`

제약:

- 실제 계약 점검은 신규 로컬 Chroma 인덱스 준비를 포함한 cold-start
  측정이다.
- Gemini embedding 응답과 Cohere Trial rerank는 token usage·과금을
  제공하지 않아 로그상 비용이 `0`이다. 따라서 실제 계약 비용은 알려진
  비용의 하한이다.
- 각 모드 1회 표본이므로 통계적 평균이 아니라 발표용 실측 기준선이다.
- 원화는 `1 USD = 1,470 KRW` 단순 환산이며 세금·실제 환율은 별도다.

`.png`는 같은 이름 `.svg`를 headless Chrome으로 2배 배율 렌더한 결과다.
SVG를 고치면 아래 명령으로 다시 만든다.

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=old `
  --disable-gpu --hide-scrollbars --force-device-scale-factor=2 `
  --window-size=1600,900 --screenshot="<절대경로>\02-evaluation-summary.png" `
  "file:///<절대경로>/02-evaluation-summary.svg"
```
