# data/processed/

원본에서 파생한 **가공 산출물** 보관 위치.

> **이 폴더 내용은 Git 제외**된다(`data/processed/**/*`). 각 하위 폴더 `README.md`만 예외. 개인정보 파생 가능성이 있으므로 커밋하지 않는다.
> 원본은 [`../raw/`](../raw/)에 두고 직접 덮어쓰지 않는다. 가공은 여기 별도 산출물로 남긴다.

## 하위 구조

| 폴더 | 내용 |
|------|------|
| `extracted-fields/` | 문서에서 추출한 필드값 (`document-fields.md` 기준) |
| `normalized-documents/` | 주소·금액·날짜·이름 정규화 결과 (`ai/normalization`) |
| `training-records/` | 파이프라인 산출을 파인튜닝/평가용으로 정리한 레코드 |

## 형식

- 추출값·정규화값·생성값을 구분해 기록한다(`document-fields.md` 필드 구분 원칙).
- 근거 부족 필드는 `정보 부족`으로 표기한다.

## 현재 상태 / TODO

- `.gitkeep`만 존재. 산출물 없음.
- 출력은 `ai/src/lease_companion_ai/schemas/`의 canonical Pydantic 모델과 `data/schemas/generated/` 생성본을 따른다.
