# 공식 원문 저장 경계

이 폴더에는 개별 게시물의 재배포 조건이 명시적으로 확인된 공식 원문만 둔다.

- `source_inventory.csv`의 `source_status=official_verified`만 허용한다.
- `usage_terms`에 `재배포 허용`이 명시되지 않은 자료는 저장하지 않는다.
- 원문 파일은 수정하지 않고 SHA-256으로 무결성을 기록한다.
- 현재 `SRC-HTA-LAW`·`SRC-HTA-DECREE`는 저작권법 제7조와 국가법령정보센터 자유이용 정책을 확인해 정규화 텍스트를 저장한다.
- 나머지 공식 출처 7개는 `metadata_only`다. 공식 URL과 검증 메타데이터만 사용한다.
- 실제 계약서·개인정보·`data/evaluation/ocr/` 자료는 이 폴더에 두지 않는다.
