# data/datasets/

(선택) 로컬 7B 성능비교 실험용 조항 분류 **파인튜닝 데이터셋** 보관 위치. 설계 기준: [`../../docs/data/training-dataset.md`](../../docs/data/training-dataset.md).

> 비식별·합성 데이터만 둔다. 실제 개인정보 금지.

## 하위 구조 (흐름)

```
source/       원천 조항 문장 (라벨 없음, 비식별·합성)
labeled/      라벨 5종 부착·검수 완료 (분할 전)
train/        학습
validation/   하이퍼파라미터·조기종료
test/         최종 평가 (학습·검증 미사용)
```

## 형식

- 항목 = 조항 문장 1건 + 라벨 5종(`clause_type·clarity·responsible_party·condition·review_required`).
- 라벨 정의: [`../labels/`](../labels/).
- 포맷(JSONL 필드 스키마)은 TODO.

## 분리 원칙

- train/validation/test를 분리한다. **동일 문장이 여러 분할에 중복되지 않게** 한다(누수 방지).
- `reviewed` 항목만 분할 대상으로 승격한다.

## 현재 상태 / TODO

- `.gitkeep`만 존재. 데이터 없음.
- TODO: 원천 문장 수집·라벨링·검수, 분할 비율·시드·건수 확정, 베이스 모델 결정(임의 확정 금지).
