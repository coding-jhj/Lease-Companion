# evaluation/

## 책임

AI 컴포넌트별·end-to-end 평가를 실행한다. 추출·정규화·로컬 분류·규칙 판정·검색·생성 단계와 전체 흐름의 품질을 측정한다. 평가 데이터는 `data/evaluation/`, 평가 계획은 `docs/ai/evaluation-plan.md`를 따른다.

## 하위 구조

- 컴포넌트별 평가 실행 (extraction / normalization / classification / rules / retrieval / generation)
- end-to-end 파이프라인 평가 실행
- 지표 집계·리포트 (train/validation/test 분리 준수)

## 입력

- `data/evaluation/`의 단계별 평가 데이터, 각 컴포넌트 출력

## 출력

- 컴포넌트별·전체 평가 지표 리포트

## TODO

- 평가 데이터셋 미구성 → 실행 보류
- **목표 성능 수치는 실제 측정 전 임의로 만들지 않는다.**
- 로컬 7B 파인튜닝 평가는 `ai/training/evaluation/`과 역할 구분 유지 (여기는 서비스 파이프라인 평가)
