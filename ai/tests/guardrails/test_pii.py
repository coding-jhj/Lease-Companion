from lease_companion_ai.guardrails.pii import PiiTokenizer, contains_raw_pii


def test_tokenizes_and_restores_supported_pii_deterministically():
    original = (
        "임대인: 홍길동, 목적물 주소: 서울특별시 종로구 새싹로 12 101동 202호, "
        "계좌번호: 110-123-456789, 주민번호 900101-1234567, "
        "전화 010-1234-5678, 이메일 user@example.com"
    )
    tokenizer = PiiTokenizer()

    tokenized = tokenizer.tokenize(original)

    assert tokenized is not None
    assert "홍길동" not in tokenized
    assert "서울특별시 종로구 새싹로 12 101동 202호" not in tokenized
    assert "110-123-456789" not in tokenized
    assert "900101-1234567" not in tokenized
    assert "010-1234-5678" not in tokenized
    assert "user@example.com" not in tokenized
    assert "[PERSON_1]" in tokenized
    assert "[ADDRESS_1]" in tokenized
    assert "[ACCOUNT_1]" in tokenized
    assert "[RESIDENT_ID_1]" in tokenized
    assert "[PHONE_1]" in tokenized
    assert "[EMAIL_1]" in tokenized
    assert not contains_raw_pii(tokenized)
    assert tokenizer.tokenize(tokenized) == tokenized
    assert tokenizer.tokenize("임대인: 홍길동") == "임대인: [PERSON_1]"
    assert tokenizer.restore(tokenized) == original


def test_does_not_tokenize_iso_dates_as_account_numbers():
    """등기 발급일자 같은 YYYY-MM-DD는 계좌번호가 아니다.

    토큰화되면 추출 프롬프트가 날짜를 판독 불가로 보고 null을 반환해
    R07(등기 최신성)이 전부 `확인 불가`로 떨어진다.
    """
    text = "발급일자: 2026-08-01\n기간 2026-08-05∼2028-08-04, 입주 2026-08-05"

    tokenizer = PiiTokenizer()
    tokenized = tokenizer.tokenize(text)

    assert tokenized == text
    assert "[ACCOUNT_1]" not in tokenized


def test_still_tokenizes_account_numbers_that_resemble_dates():
    """날짜 예외가 실제 계좌번호까지 통과시키면 안 된다."""
    tokenizer = PiiTokenizer()

    for account in ("1002-123-456789", "110-123-456789", "2026-98-01"):
        tokenized = tokenizer.tokenize(f"입금 계좌 {account}")
        assert account not in tokenized, account
        assert tokenizer.restore(tokenized) == f"입금 계좌 {account}"


def test_restores_tokens_even_when_model_drops_brackets():
    """Gemini가 JSON 배열에 `PERSON_1`처럼 대괄호를 빼고 낼 때가 있다.

    복원하지 못하면 owner_names에 토큰 문자열이 그대로 남아 R01이 무너진다.
    """
    tokenizer = PiiTokenizer()
    tokenizer.tokenize("소유자 배온유, 임대인 남도경")

    assert tokenizer.restore("PERSON_1") == "배온유"
    assert tokenizer.restore("[PERSON_2]") == "남도경"
    assert tokenizer.restore("소유자: PERSON_1") == "소유자: 배온유"
    # 발급되지 않은 토큰 이름은 건드리지 않는다.
    assert tokenizer.restore("PERSON_9") == "PERSON_9"
    # 토큰과 무관한 평범한 문장은 그대로 둔다.
    assert tokenizer.restore("계약서를 확인하세요") == "계약서를 확인하세요"


def test_does_not_tokenize_ordinary_rule_language_as_name_or_address():
    text = "계약서와 등기사항증명서의 목적물 주소가 일치하는지 확인하십시오."

    assert PiiTokenizer().tokenize(text) == text
    assert not contains_raw_pii(text)
