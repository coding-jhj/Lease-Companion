# data/schemas/

문서 필드·산출물 **JSON 스키마** 보관 위치. 필드 정의: [`../../docs/data/document-fields.md`](../../docs/data/document-fields.md).

## 책임

- 계약서·등기사항증명서·중개대상물 확인설명서·건축물대장의 추출 필드 스키마.
- 추출·정규화 산출물 스키마(`processed/`와 정합).
- 판정 결과 리포트 스키마(공통 9개 상태·5개 시급도·J01–J12와 정합, [`../../docs/data/judgment-spec.md`](../../docs/data/judgment-spec.md)).

## 형식

- 필드별 데이터 타입·필수/선택·검증 규칙을 명시한다.
- 추출값·정규화값·생성값을 구분한다.

## 현재 상태 / TODO

- `.gitkeep`만 존재. 스키마 없음.
- TODO: `document-fields.md`를 JSON 스키마로 확정, 판정 리포트 스키마 작성.
