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
