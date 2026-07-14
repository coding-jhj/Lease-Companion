# training/

## 책임

> **(선택) 상용 vs 로컬 성능비교 실험용 — MVP 크리티컬 패스 제외.** 파인튜닝 B/C안 검증 목적이며, MVP 조항 구조화·필드 추출은 상용 LLM(Gemini 3.5 Flash)이 담당한다.

로컬 7B 모델 QLoRA 파인튜닝 코드·설정·메타데이터를 관리한다. 입력=임대차 계약서·특약 문장, 출력=`clause_type`·`clarity`·`responsible_party`·`condition`·`review_required`. 7B 4bit QLoRA로 조항 유형·명확성 후보 분류를 학습한다. **모델 가중치·체크포인트는 Git에 커밋하지 않는다.** 학습 설정·전처리·평가 코드·메타데이터만 커밋한다.

## 하위 구조

- `configs/` — 학습 하이퍼파라미터·QLoRA 설정 (베이스 모델은 TODO로 표기)
- `preprocessing/` — 라벨 데이터를 학습 형식으로 전처리 (train/validation/test 분리)
- `qlora/` — 4bit QLoRA 파인튜닝 실행 스크립트
- `evaluation/` — 파인튜닝 모델 평가 (조항 분류·명확성 후보 지표)
- `notebooks/` — 데이터 탐색·실험 노트북

## 입력

- `data/`의 파인튜닝 데이터셋 (비식별·합성, 라벨: `clause_type`·`clarity`·`responsible_party`·`condition`·`review_required`)

## 출력

- QLoRA 어댑터 가중치 (**Git 제외**, 서빙 시 `local_model/adapters/`가 로드)
- 학습·평가 메타데이터·지표 (커밋)

## TODO

- **베이스 모델 미정** → 학습 실행 보류, config 자리표시만
- 라벨 스키마·데이터셋 구성 확정 필요
- **목표 성능 수치는 실제 측정 전 임의로 만들지 않는다.**
- 이번 정비는 스캐폴딩·설계 단계. 모델 다운로드·학습 실행은 하지 않는다.
