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


def test_does_not_tokenize_ordinary_rule_language_as_name_or_address():
    text = "계약서와 등기사항증명서의 목적물 주소가 일치하는지 확인하십시오."

    assert PiiTokenizer().tokenize(text) == text
    assert not contains_raw_pii(text)
