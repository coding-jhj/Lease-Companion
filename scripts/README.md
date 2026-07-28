# scripts/

프로젝트 보조 스크립트 보관 위치. (데이터 준비·평가 실행 등)

## 원칙

- 실제 개인정보·비밀정보를 스크립트에 하드코딩하지 않는다.
- 파괴적 동작(삭제·덮어쓰기)은 명시적 확인 후 수행하도록 작성한다.

## 현재 상태

- `run-minimum-mvp.ps1` — 최소 MVP 데모 서버 실행(PYTHONPATH 설정 후 uvicorn `app.mvp_app:app`, 127.0.0.1:8000).
- `generate_unified_schemas.py` — canonical Pydantic 모델에서 JSON Schema 생성.
- `generate_case001_fixture.py` — CASE-001 canonical fixture 생성.
- `prepare_rag_sources.py` — 공식 검증 source inventory에서 결정적 RAG manifest 생성. 원문 재배포 허용을 추정하지 않는다.
- `collect_verified_law_sources.py` — 자유이용이 확인된 국가법령정보센터 법령 2개의 공식 본문을 정규화해 수집.
- `evaluate_retrieval.py` — `--split dev|test|all`로 로컬 BM25 retrieval을 분리 평가.
- `evaluate_ai_pipeline.py` — 외부 provider 호출 없이 A 파이프라인 test 기준선을 생성.
- `evaluate_ragas_offline.py` — 외부 provider 호출 없이 일반·특약 RAG의 RAGAS ID Precision·Recall 기준선을 생성.
- `evaluate_ragas_online.py` — Gemini judge·embedding으로 Faithfulness·Response Relevancy 측정. 유료 호출 있음.
- `generate_provider_report.py` — provider JSONL 메타데이터를 발표용 JSON·CSV·SVG로 집계. 외부 호출 없음.
- `measure_gemini_ttfb.py` — 개인정보 없는 합성 prompt를 Gemini streaming으로 반복 호출해 실제 TTFB 기록.
- `collect_mode_cycle_metrics.py` — 실제 계약 점검 또는 승인된 3턴 시뮬레이션의 전체 1사이클 provider 메타데이터를 별도 JSONL로 기록.
- `generate_ppt_metrics_assets.py` — Offline/Online RAGAS와 모드별 사이클 요약을 PPT용 CSV·SVG로 생성.
