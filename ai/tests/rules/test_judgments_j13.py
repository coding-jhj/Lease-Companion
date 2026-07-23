from __future__ import annotations

from lease_companion_ai.rules.judgments import _j13
from lease_companion_ai.schemas.unified import RuleStatus


def _judgment_input(*, present, special, issue_code=None):
    """J13 입력만 담은 최소 JudgmentInput을 만든다."""
    from lease_companion_ai.schemas.unified import (
        Confidence,
        ContractContext,
        ExtractedField,
        JudgmentInput,
        VerificationStatus,
    )

    def _field(name, value, code=None):
        from lease_companion_ai.schemas.unified import FieldIssueCode

        return ExtractedField(
            field_name=name,
            extracted_value=value,
            confidence=Confidence.EXTRACTED if value is not None else Confidence.FAILED,
            verification_status=VerificationStatus.CONFIRMED,
            issue_code=code if value is not None else (code or FieldIssueCode.NOT_APPLICABLE),
            failure_reason=None if value is not None else "테스트용 판독 실패",
        )

    return JudgmentInput(
        input_snapshot_id="SNAP-J13-TEST",
        contract_id=1,
        judgment_ids=("J13",),
        contract_fields={
            "special_clauses_present": _field("special_clauses_present", present),
            "special_clauses": _field("special_clauses", special, issue_code),
        },
        registry_fields={},
        contract_context=ContractContext(
            contract_id=1,
            contract_type="전세",
            contract_stage="서명 전",
            deposit_paid=False,
            signed=False,
        ),
        classification_candidates=(),
    )


def _judgment_input_bypassing_field_validation(*, present, special):
    """정상 스키마 경로로는 만들 수 없는 방어 분기(비-list, 빈 list)를 재현한다.

    ExtractedField·JudgmentInput은 각각 '빈 목록'과 '잘못된 타입' 값을 생성 시점에
    막는다. 그래도 ``_j13`` 안에는 이를 대비하는 방어 분기가 남아 있으므로,
    ``model_construct``로 검증을 건너뛰어 그 분기가 실제로 무엇을 반환하는지 확인한다.
    """
    from lease_companion_ai.schemas.unified import (
        Confidence,
        ContractContext,
        ExtractedField,
        JudgmentInput,
        VerificationStatus,
    )

    special_field = ExtractedField.model_construct(
        field_name="special_clauses",
        extracted_value=special,
        normalized_value=None,
        user_corrected_value=None,
        confidence=Confidence.EXTRACTED,
        verification_status=VerificationStatus.CONFIRMED,
        issue_code=None,
        failure_reason=None,
    )
    present_field = ExtractedField(
        field_name="special_clauses_present",
        extracted_value=present,
        confidence=Confidence.EXTRACTED,
        verification_status=VerificationStatus.CONFIRMED,
    )
    return JudgmentInput.model_construct(
        input_snapshot_id="SNAP-J13-TEST",
        contract_id=1,
        case_id=None,
        judgment_ids=("J13",),
        contract_fields={
            "special_clauses_present": present_field,
            "special_clauses": special_field,
        },
        registry_fields={},
        contract_context=ContractContext(
            contract_id=1,
            contract_type="전세",
            contract_stage="서명 전",
            deposit_paid=False,
            signed=False,
        ),
        classification_candidates=(),
    )


def test_j13_is_not_applicable_when_no_special_clauses():
    assert _j13(_judgment_input(present=False, special=None)) is RuleStatus.NOT_APPLICABLE


def test_j13_is_not_applicable_when_clauses_match_no_j13_catalog_entry():
    clauses = ["임대차계약과 관련한 분쟁은 주택임대차분쟁조정위원회 조정을 신청할 수 있다."]
    assert _j13(_judgment_input(present=True, special=clauses)) is RuleStatus.NOT_APPLICABLE


def test_j13_cannot_check_when_clause_text_is_unreadable():
    from lease_companion_ai.schemas.unified import FieldIssueCode

    result = _j13(
        _judgment_input(present=True, special=None, issue_code=FieldIssueCode.PARSE_FAILED)
    )
    assert result is RuleStatus.CANNOT_CHECK


def test_j13_cannot_check_when_special_is_none_but_present_is_true():
    result = _j13(_judgment_input(present=True, special=None))
    assert result is RuleStatus.CANNOT_CHECK


def test_j13_cannot_check_when_special_is_not_a_list():
    result = _j13(
        _judgment_input_bypassing_field_validation(
            present=True, special="특약 원문 문자열 하나"
        )
    )
    assert result is RuleStatus.CANNOT_CHECK


def test_j13_cannot_check_when_clause_list_is_empty_but_present_is_true():
    result = _j13(_judgment_input_bypassing_field_validation(present=True, special=[]))
    assert result is RuleStatus.CANNOT_CHECK


def test_j13_cannot_check_when_clause_list_has_only_whitespace_but_present_is_true():
    result = _j13(_judgment_input(present=True, special=["   ", "\t"]))
    assert result is RuleStatus.CANNOT_CHECK


def test_j13_not_applicable_when_clause_list_is_empty_and_present_is_false():
    result = _j13(_judgment_input_bypassing_field_validation(present=False, special=[]))
    assert result is RuleStatus.NOT_APPLICABLE
