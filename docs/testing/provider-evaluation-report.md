# Provider 평가·호출 로그 발표 자료

Gemini·Cohere 실호출 시 계약 원문·프롬프트 없이 호출 메타데이터만 JSONL로
기록하고, JSON·CSV·SVG 발표 자료로 집계한다.

## Cohere Evaluation key

2026-07-28 공식 문서 확인 기준:

- Evaluation/Trial key는 무료이며 사용량 제한이 있다.
- Rerank Trial 한도는 분당 10회다.
- Trial key 전체 한도는 월 1,000 API 호출이다.
- 교육생의 비상업 프로젝트 검증에는 Evaluation key를 사용할 수 있다.
- Cohere 이용약관은 성능 모니터링·benchmarking·경쟁 목적 접근을 금지한다.
  본 프로젝트 내부 RAG 동작 검증에 사용하고, Cohere 모델 성능 비교
  벤치마크 공개가 필요하면 Cohere에 사전 문의한다.

공식 근거:

- <https://docs.cohere.com/docs/rate-limits>
- <https://cohere.com/terms-of-use>

## 계측 활성화

루트 `.env`에 다음을 설정한다.

```dotenv
PROVIDER_METRICS_JSONL=outputs/provider-metrics/provider-calls.jsonl
```

비용 추정이 필요하면
`data/evaluation/config/provider-pricing.example.json`을 Git 제외 경로인
`provider-pricing.local.json`으로 복사하고, 실행일의 공식 가격만 입력한다.

```dotenv
PROVIDER_PRICING_JSON=data/evaluation/config/provider-pricing.local.json
```

가격표에 없는 모델 비용은 `null`이다. 임의 단가나 오래된 단가를 사용하지
않는다. Evaluation key의 실제 청구 비용이 0이어도, `search_units` 사용량은
별도로 기록한다.

기록 필드:

- `timestamp`, `provider`, `model`, `task`, `status`, `attempt`
- `latency_ms`, `ttfb_ms`
- `input_tokens`, `output_tokens`, `cached_tokens`, `search_units`
- `estimated_cost`, `currency`, `pricing_version`

운영 구조화 SDK 호출은 비스트리밍이다. `latency_ms`는 전체 응답 시간이며,
`ttfb_ms`는 혼동 방지를 위해 `null`로 기록한다. 실제 TTFB는 개인정보 없는
합성 prompt를 쓰는 별도 streaming runner로 측정한다.

```powershell
python scripts/measure_gemini_ttfb.py `
  --output outputs/provider-metrics/gemini-ttfb.jsonl `
  --runs 10 `
  --requests-per-minute 5
```

runner는 `generate_content_stream()` 호출 시작부터 첫 chunk 수신까지를
`ttfb_ms`, 마지막 chunk까지를 `latency_ms`로 기록한다. 각 표본의 독립성을
유지하기 위해 자동 재시도하지 않는다.

## 발표 자료 생성

```powershell
python scripts/generate_provider_report.py `
  --input outputs/provider-metrics/provider-calls.jsonl `
  --output-dir outputs/provider-metrics/report
```

산출물:

- `provider-summary.json`: 원본 집계 데이터
- `provider-summary.csv`: PPT 표·Excel용
- `provider-latency.svg`: PPT 삽입용 평균 응답시간 그래프
- `provider-ttfb.svg`: PPT 삽입용 실제 평균 TTFB 그래프

평균만으로 변동성을 숨기지 않도록 호출 수·성공/실패 수·평균·P95를 함께
제시한다. 실제 개인정보·계약 원문은 provider와 로그에 보내지 않는다.
