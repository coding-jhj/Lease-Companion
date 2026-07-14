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

- 폴더 구조·하위 README 존재. 실제 데이터 없음.
- TODO: 문서 필드 스키마 초안 (`docs/data/document-fields.md` 기반) → `schemas/`.
- TODO: 규칙 데이터 정의 (`docs/data/rule-definition.md`·`judgment-spec.md` 기반) → `rules/`.
- TODO: 라벨 정의·경계 사례 문서화 → `labels/`.
- TODO: 파인튜닝 데이터셋 수집·라벨링·분할 (`docs/data/training-dataset.md` 기준) → `datasets/`.
- TODO: 공식 RAG 출처 수집·메타데이터 기록 (`docs/data/rag-sources.md` 기준) → `rag/`.
- TODO: 단계별 평가 데이터셋 구성 (`docs/ai/evaluation-plan.md` 기준) → `evaluation/`.
