# data/labels/

(선택) 로컬 7B 성능비교 실험용 조항 분류 **라벨 체계** 정의 보관 위치. 데이터셋: [`../datasets/`](../datasets/), 기준: [`../../docs/data/training-dataset.md`](../../docs/data/training-dataset.md).

## 라벨 5종 ↔ 폴더

| 폴더 | 라벨 | 의미 |
|------|------|------|
| `clause-types/` | `clause_type` | 조항 유형 (보증금·차임·관리비·계약기간·원상복구·반환조건 등) |
| `clarity/` | `clarity` | 명확 / 불명확 |
| `responsible-party/` | `responsible_party` | 임대인 / 임차인 / 공동 / 불명확 / 해당없음 |
| `judgment-status/` | (매핑 참조) | 라벨 → 판정 상태 매핑 근거 |

> `condition`(명시/미명시)·`review_required`(true/false)는 값이 단순해 별도 폴더 없이 `clarity`/`judgment-status` 문서에 정의한다.

## 형식

- 각 폴더에 **라벨 값 목록·정의·경계 사례**를 문서화한다.
- `judgment-status/`는 라벨이 판정 명세([`../../docs/data/judgment-spec.md`](../../docs/data/judgment-spec.md))의 공통 9개 상태와 어떻게 연결되는지 기록한다. **로컬 7B 출력은 판정 상태를 직접 확정하지 않는다**(규칙 엔진이 확정).

## 현재 상태 / TODO

- `.gitkeep`만 존재. 라벨 정의 없음.
- TODO: 라벨 값 확정, 경계 사례·라벨링 가이드 작성.
