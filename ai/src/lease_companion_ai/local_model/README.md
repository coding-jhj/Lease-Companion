# local_model/

## 책임

파인튜닝한 **로컬 7B 모델**로 임대차 조항의 유형과 명확성 후보를 1차 분류한다. 조항 유형·명확/불명확/확인 필요 후보·책임 주체·조건을 구조화한다. **최종 판정을 내리지 않는다.** 명시적 비교·판정은 `rules/`가 담당한다.

## 하위 구조

- `inference/` — 로컬 7B 추론 실행 (4bit 로드, 프롬프트 구성)
- `adapters/` — QLoRA 어댑터 로드·교체 (가중치는 Git 제외)
- `confidence/` — 출력 신뢰도 산정, 저신뢰 결과에 상용 LLM 재검토 플래그
- `output_parser/` — 모델 출력을 `clause_type`·`clarity`·`responsible_party`·`condition`·`review_required` 필드로 파싱

## 입력

- 임대차 계약서·특약 조항 문장 (추출·정규화 후)

## 출력

- 조항별 `clause_type` / `clarity` / `responsible_party` / `condition` / `review_required` 후보 + 신뢰도
- 저신뢰 항목은 `routing/`을 거쳐 상용 LLM 재검토 대상으로 표시

## TODO

- 베이스 모델 미정 → 추론·어댑터 로드 경로 보류
- 파인튜닝 산출물은 `ai/training/`, 가중치·체크포인트는 Git 미포함
- 신뢰도 임계값·재검토 라우팅 기준 확정 필요
