# 로컬 7B 파인튜닝 계획

로컬 7B 모델(`ai/src/lease_companion_ai/local_model/`) 파인튜닝 과제·데이터·산출물 관리 규칙을 정의한다. 이 문서는 계획이며, 실제 학습 실행·가중치 생성은 포함하지 않는다.

## 과제 정의 (확정)

임대차 계약서·특약 문장을 조항 유형·명확성 등으로 분류하는 **구조화 분류** 과제.

- **입력**: 계약서·특약 문장 (문장 또는 조항 단위)
- **출력(구조화 JSON)**: `clause_type` · `clarity` · `responsible_party` · `condition` · `review_required`

출력 형식은 `local-model-plan.md` 및 `ai/src/lease_companion_ai/schemas/`와 일치시킨다.

## 학습 방식 (확정)

- 7B 모델, **4bit QLoRA** 파인튜닝
- Colab에서 학습·평가
- 데이터 **train / validation / test 분리**
- 구조화 JSON 스키마 준수를 학습·평가 목표에 포함

## 코드 위치 (확정)

`ai/training/` (src 밖, `ai/` 직속):

- `configs/` — 학습 하이퍼파라미터·QLoRA 설정 (베이스 모델 TODO)
- `preprocessing/` — 라벨 데이터를 학습 형식으로 전처리 (train/validation/test 분리)
- `qlora/` — 4bit QLoRA 파인튜닝 실행 스크립트
- `evaluation/` — 파인튜닝 모델 평가 (조항 분류·명확성 후보 지표)
- `notebooks/` — 데이터 탐색·실험 노트북

서빙 시 어댑터는 `src/lease_companion_ai/local_model/adapters/`가 로드한다(가중치 Git 제외). `training/evaluation/`(파인튜닝 평가)과 `src/.../evaluation/`(서비스 파이프라인 평가)의 역할을 구분한다.

## 데이터 (확정)

- 라벨·파인튜닝 데이터셋은 `data/` 하위에서 참조·관리한다. (비식별·합성 데이터만)
- train/validation/test 분리를 유지한다.
- 실제 개인정보·계약 문서는 커밋하지 않는다.

## 저장소 포함 / 제외 (확정)

| 포함 (Git) | 제외 (Git) |
|------------|------------|
| 학습·전처리 설정 (`ai/training/`) | 모델 가중치 |
| 전처리 스크립트 | 체크포인트 |
| 평가 스크립트·결과 형식 | 대용량 어댑터 산출물 |
| 데이터셋 메타데이터·라벨 스키마 | 실제 개인정보·계약 문서 |

가중치·체크포인트는 Git에 커밋하지 않는다. 저장소에는 **설정·전처리·평가·메타데이터**만 둔다.

## 평가 연계

- 베이스 7B vs 파인튜닝 7B 비교, 조항 유형 분류 P·R·F1, 명확성 분류 성능, 구조화 JSON 스키마 준수율, 로컬 모델 신뢰도. 정의·기록 형식: [`evaluation-matrix.md`](evaluation-matrix.md).
- 목표 수치는 실제 측정 전 임의로 만들지 않는다.

## 미정 (TODO)

- 베이스 7B 모델
- 하이퍼파라미터(rank·learning rate·epoch 등)
- 데이터셋 규모·라벨링 절차
