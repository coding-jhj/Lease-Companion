# 공통 오류 응답 형식

> 2026-07-16 회원 API 구현에서 확정. 이후 모든 API가 이 형식을 따른다.

## 방향

- 모든 오류는 일관된 구조로 반환한다.
- 개인정보·문서 내용을 오류 메시지·로그에 포함하지 않는다. (422 응답에 사용자가 입력한 값을 되돌려주지 않는다)
- 사용자에게 노출하는 메시지와 내부 디버그 정보를 분리한다.

## 확정 형식

```json
{
  "error": {
    "code": "validation_error",
    "message": "입력값이 올바르지 않습니다.",
    "details": [
      {"loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error"}
    ]
  }
}
```

| 필드 | 의미 |
|------|------|
| `error.code` | 기계 판별용 오류 코드. **소문자 snake_case** |
| `error.message` | 사용자 표시용 한국어 메시지 (개인정보 미포함, 화면에 그대로 노출 가능) |
| `error.details` | 검증 오류(422)일 때만 존재. 필드 단위 정보 배열 — `loc`(위치)·`msg`·`type` |

## 확정 코드 목록 (구현된 것)

| code | HTTP | 의미 |
|------|------|------|
| `validation_error` | 422 | 입력 형식 오류 전부. 어느 필드인지는 `details[].loc`으로 판별 (필드별 코드를 만들지 않는다) |
| `invalid_credentials` | 401 | 로그인 실패 (아이디 없음/비밀번호 틀림 구분 없이 동일 응답) |
| `unauthorized` | 401 | 토큰 없음·만료·무효 상태로 보호된 API 호출 |
| `username_taken` | 409 | 가입 시 아이디 중복 |
| `email_taken` | 409 | 가입 시 이메일 중복 |
| `not_found` | 404 | 리소스 없음. 남의 계약 건 접근·없는 모의 등기 case_id도 동일 응답 (존재 여부 노출 방지) |
| `unsupported_file_type` | 422 | 업로드 파일 형식이 pdf·jpg·jpeg·png가 아님 |
| `empty_file` | 422 | 빈 파일 업로드 |
| `file_too_large` | 422 | 업로드 파일 20MB 초과 |
| `missing_contract_document` | 422 | 추출 실행 시 업로드된 계약서 없음 |
| `missing_registry_source` | 422 | 추출 실행 시 등기 문서·모의 등기 연결 둘 다 없음 |
| `extraction_not_ready` | 422 | 완료된 추출 결과가 없는 상태에서 수정·확인 요청 |
| `invalid_correction_request` | 422 | 수정 요청이 통합 CorrectionRequest 스키마 검증 실패 |
| `unknown_correction_field` | 422 | 수정 대상 필드가 추출 결과에 없음 |
| `contract_id_mismatch` | 422 | 요청 본문의 contract_id가 경로의 계약 건과 다름 |
| `no_confirmed_snapshot` | 422 | 확인 완료된 추출값 없이 분석 실행 요청 |

새 API에서 코드를 추가하는 것은 자유(소문자 snake_case 준수), 기존 코드 변경은 팀 공유 후에만.

## 다뤄야 할 오류 범주

- 입력 검증 실패 (형식·크기·필수값)
- 업로드 파일 형식·크기 초과
- 인증·권한 실패 (미인증, 계약 건 소유자 아님)
- 외부 AI 호출 실패·시간 초과·잘못된 출력
- 계약 건·문서·분석 실행·결과 등 리소스 없음
- 서버 내부 오류

## 미정 (TODO)

- HTTP 상태 코드 매핑, 오류 코드 체계, 다국어 메시지 여부
