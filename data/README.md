# data/

슬기로운 계약생활의 데이터 계층. 입력·분석 기준·라벨·파인튜닝·RAG·평가·모델 메타데이터를 관리한다.

전용 규칙은 [`AGENTS.md`](AGENTS.md), 데이터 설계 문서는 [`../docs/data/`](../docs/data/).

## 담당 데이터 (구분)

- **입력 데이터**: 계약서·특약, 등기사항증명서, 중개대상물 확인설명서, 건축물대장 (실제 원본은 Git 제외 → `raw/`)
- **분석 기준 데이터**: 문서 필드 스키마, 문서 비교 규칙, 라벨 체계, 공식 RAG 자료·메타데이터
- **가공·학습 데이터**: 정규화 문서, 추출 필드, 학습 레코드, 파인튜닝 데이터셋
- **평가·메타데이터**: 단계별 평가 데이터, 모델 메타데이터(가중치 제외)

## 하위 구조

```
raw/                     실제 원본 (Git 제외, README만 커밋)
sample/                  비식별·합성 샘플
  contracts/ registry-records/ explanation-sheets/ building-ledgers/ expected-results/
processed/               가공 산출물 (Git 제외, 각 README만 커밋)
  extracted-fields/ normalized-documents/ training-records/
schemas/                 문서 필드 JSON 스키마
rules/                   문서 비교 규칙 (정의: docs/data/rule-definition.md)
reference-cases/         DP01~DP08 표시용 검증 공개 사례 메타데이터 (공식 근거와 분리)
labels/                  (선택) 로컬 7B 성능비교 실험 라벨 체계
  clause-types/ clarity/ responsible-party/ judgment-status/
datasets/                파인튜닝 데이터셋 (docs/data/training-dataset.md)
  source/ labeled/ train/ validation/ test/
rag/                     공식 근거 자료
  sources/ chunks/ metadata/ evaluation/
evaluation/              단계별 평가 데이터
  extraction/ local-model/ rules/ retrieval/ generation/ routing/ end-to-end/
model-metadata/          모델 메타데이터 (가중치 제외)
  base-models/ adapters/ experiment-results/
```

## 저장해야 하는 파일

- 가상·비식별 샘플, 필드 스키마, 규칙·라벨 데이터, 파인튜닝 데이터셋(비식별), 공식 RAG 자료·메타데이터, 평가 데이터, 모델 **메타데이터**.

## 저장하면 안 되는 파일

- 실제 계약서·개인정보 (이름·주소·연락처·계좌번호 등) → `raw/` 밖에 두지 않으며 `raw/`는 Git 제외.
- 모델 가중치·체크포인트·어댑터 파일 (→ 메타데이터만 `model-metadata/`).
- 대용량 벡터 인덱스 (→ Git 제외).

## 다른 폴더와의 연결

- `ai/`가 스키마·규칙·라벨·RAG 자료·데이터셋·평가 데이터를 참조한다.
- 데이터 설계 문서는 [`../docs/data/`](../docs/data/) (판정 명세·문서 필드·규칙·RAG·개인정보·파인튜닝 데이터셋).

## 현재 상태 / TODO

- 비식별·합성 계약서·등기 샘플, 규칙 CSV, 평가 goldset, canonical JSON Schema 16개와 CASE-001 fixture 9개가 존재한다.
- `schemas/generated/`만 canonical Pydantic v1.8.0 읽기 호환·v1.9.0 신규 출력 생성본이며 `schemas/legacy/`는 과거 설계 참고자료다.
- `rules/source_inventory.csv`의 공식자료 후보 16개는 공식 검증·합성 참고·미검증·제외로 분류했다.
- `rules/rule_evidence_map.csv`와 dev/test RAG goldset은 `official_verified` source ID만 허용하도록 계약 검사를 적용했다.
- 공식 검증 10개 manifest와 로컬 원문 6개(법령 3개·법령 서식 1개·표준계약서 1개·안심 전세계약 체크리스트 1개)·SHA-256이 `rag/metadata`·`rag/sources`에 있다. 체크리스트는 2026-07-20 팀 예외 규정으로 적재했다. 나머지 4개는 원문 재배포 조건 때문에 metadata-only다.
- `rag/evaluation/`에 분리된 dev/test retrieval 실측 결과가 있다. 로컬 검색 가능한 원문은 6개다.
- `reference-cases/verified_reference_cases.json`에 외부 API 호출 없이 표시하는 HUG 유형 안내와 익명 분쟁조정 사례 메타데이터가 있다. 이 목록은 R/J 판정과 공식 근거를 변경하지 않는다.
- `scripts/evaluate_ai_pipeline.py`가 추출·사용자 수정·R01~R10·J01~J12·R/J template 생성·J 검색 계약·Guardrail·PII·end-to-end의 외부 호출 없는 평가를 실행한다. 최신 결과는 `evaluation/results/offline_test_metrics.json`에 기록한다.
- TODO: 라벨 정의·경계 사례 문서화 → `labels/`.
- TODO: 파인튜닝 데이터셋 수집·라벨링·분할 (`docs/data/training-dataset.md` 기준) → `datasets/`.
- TODO: metadata-only 공식자료 5개의 이용조건을 확인해 허용되는 원문만 추가하고 retrieval 평가를 다시 측정한다.
- TODO: 독립 routing 평가 데이터셋·실행기를 구성하고, 승인된 실제 provider의 생성 품질·지연시간·비용 기준선을 측정한다 (`docs/ai/evaluation-plan.md`).
