# 문서 필드 정의

> 문서별 주요 추출 필드 정의. 확정 JSON 스키마는 [`data/schemas/`](../../data/schemas/)에 별도로 둔다.
> 이 문서의 필드는 판정 명세([`judgment-spec.md`](judgment-spec.md)) J01–J12의 입력이 된다. 필드를 바꾸면 판정 명세도 함께 확인한다.

## 필드 구분 원칙

- **추출값(extracted)**: 문서에서 그대로 읽은 값. 상용 LLM 구조화(Gemini 3.5 Flash)·OCR(상용 LLM Gemini 3.5 Flash VLM 통합)·디지털 PDF 텍스트 추출(PyMuPDF·PDF.js)이 담당한다(선택적으로 로컬 7B 성능비교 실험).
- **정규화값(normalized)**: 문서 간 비교를 위해 표준형으로 변환한 값(`ai/normalization`).
- **생성값(generated)**: 설명·질문·행동 등 LLM이 만든 값. 추출값과 절대 섞지 않는다.
- 근거 부족 필드는 `정보 부족`으로 표기한다. 값을 지어내지 않는다.

## Canonical 키·타입

schema v1.8.0의 `JudgmentInput`이 사용하는 타입을 고정한다. 모든 값은 `ExtractedField` 안에 있으며 아래는 `effective_value` 타입이다. `null`은 허용하되 J 입력에서는 `issue_code`가 필요하다.

| 문서 | 키 | 타입 |
|---|---|---|
| 계약서 | `landlord_name`, `property_address`, `account_holder`, `agent_name`, `agent_relationship` | `string | null` |
| 계약서 | `proxy_authority_documents`, `management_fee_items`, `main_clauses`, `special_clauses` | `string[] | null` |
| 계약서 | `deposit`, `monthly_rent`, `contract_payment`, `balance_payment`, 각 `*_korean_amount`, `management_fee` | `integer | null` |
| 계약서 | `contract_payment_date`, `balance_payment_date`, `move_in_date`, `start_date`, `end_date` | `YYYY-MM-DD string | null` |
| 계약서 | `management_fee_present`, `special_clauses_present`, `rights_change_clause_present` | `boolean | null` |
| 계약서 | `deposit_return_condition`, `deposit_return_clause`, `repair_responsibility`, `repair_responsibility_clause` | `string | null` |
| 등기사항증명서 | `owner_names` | `string[] | null` |
| 등기사항증명서 | `is_joint_ownership` | `boolean | null` |
| 등기사항증명서 | `owner_shares` | `object<string,string> | null` (`소유자명 → 분자/분모`) |
| 등기사항증명서 | `property_address` | `string | null` |

## 계약서 / 특약 (contracts) — 필수 문서

| 필드 | 정규화 | 관련 판정 |
|------|--------|-----------|
| 임대인 성명 | 이름 정규화 | J01 |
| 임차인 성명 | 이름 정규화 | — |
| 대리인 성명·관계 (있을 때) | 이름 정규화 | J04 |
| 대리 권한 서류 언급 여부 (위임장·인감 등) | — | J04 |
| 목적물 주소 | 주소 정규화 | J02 |
| 보증금 (숫자·한글 표기) | 금액 정규화 | J06, J07 |
| 차임(월세) (숫자·한글 표기) | 금액 정규화 | J06, J07 |
| 계약금 | 금액 정규화 | J06 |
| 잔금 | 금액 정규화 | J06 |
| 관리비 금액 | 금액 정규화 | J09 |
| 관리비 포함 항목 (수도·인터넷 등) | — | J09 |
| 계약금 지급일 | 날짜 정규화 | J08 |
| 잔금 지급일 | 날짜 정규화 | J08 |
| 입주(인도)일 | 날짜 정규화 | J08 |
| 계약 기간 (시작일·종료일) | 날짜 정규화 | J08 |
| 입금 계좌 명의 | 이름 정규화 | J05 |
| 보증금 반환 시점·조건 특약 | — | J10 |
| 수리·원상복구 책임 특약 | — | J11 |
| 주요 특약 항목 (전체) | — | J12 |

## 등기사항증명서 (registry-records) — 선택 문서(교차검증)

| 필드 | 정규화 | 관련 판정 |
|------|--------|-----------|
| 소유자 성명 | 이름 정규화 | J01 |
| 공동소유자 여부·지분 | — | J03 |
| 소재지 주소 | 주소 정규화 | J02 |
| (근)저당권 등 권리관계 항목 | — | 참고(D영역 행동 안내) |

## 중개대상물 확인설명서 (explanation-sheets) — 선택 문서

| 필드 | 정규화 | 관련 판정 |
|------|--------|-----------|
| 소재지 주소 | 주소 정규화 | J02 참고 |
| 권리관계 기재 사항 | — | 참고 |
| 관리비 관련 기재 | — | J09 참고 |

## 건축물대장 (building-ledgers) — 선택 문서(PoC 참고 범위)

| 필드 | 정규화 | 관련 판정 |
|------|--------|-----------|
| 소재지 주소 | 주소 정규화 | J02 참고 |
| 용도 | — | 참고 |
| 위반건축물 여부 | — | 참고(D영역 행동 안내) |

## 정규화 대상

- **주소·금액·날짜·이름**을 문서 간 비교 가능한 표준형으로 변환한다.
- 금액은 숫자값과 원문(숫자·한글) 표기를 함께 보존한다(J07 표기 일치 비교에 필요).
- 정규화 실패·모호 값은 플래그로 표시하고 값을 단정하지 않는다.

## 미정 (TODO)

- 문서 유형 추가 여부(임대차 신고 필증 등).
- OCR/VLM 신뢰도 수치 필드 포함 여부(현행 3등급 confidence 유지).
