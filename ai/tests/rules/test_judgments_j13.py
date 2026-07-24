from __future__ import annotations

import pytest

from lease_companion_ai.rules.judgments import _j13, _j13_matched_catalog_ids
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


@pytest.mark.parametrize(
    "clause",
    [
        "임차인은 전입신고를 하지 않기로 한다.",
        "임차인은 계약갱신요구권을 행사하지 아니한다.",
        "임대인이 주택을 매도하는 경우 새 소유자는 본 계약을 승계하지 아니한다.",
        "임차인은 전세권 설정을 요구하지 아니한다.",
        "임대인은 전세보증금반환보증 가입에 협조하지 아니한다.",
    ],
)
def test_j13_flags_protection_restriction_clauses(clause):
    assert _j13(_judgment_input(present=True, special=[clause])) is RuleStatus.CHECK_NEEDED


@pytest.mark.parametrize(
    "clause",
    [
        "주택을 인도받은 임차인은 전입신고와 확정일자를 받기로 한다.",
        "임대차계약과 관련하여 분쟁이 있는 경우 주택임대차분쟁조정위원회에 조정을 신청할 수 있다.",
        "주택의 철거 또는 재건축 계획이 있는 경우 임대인은 이를 임차인에게 고지한다.",
        "상세주소가 없는 경우 임차인의 상세주소 부여 신청에 임대인은 협조한다.",
    ],
)
def test_j13_does_not_flag_standard_protection_clauses(clause):
    assert _j13(_judgment_input(present=True, special=[clause])) is RuleStatus.NOT_APPLICABLE


# --- 최종 코드 리뷰 Finding 1: 임차인 보호 특약이 오탐되면 안 된다 -------------------


@pytest.mark.parametrize(
    "clause",
    [
        "임대인은 임차인이 전입신고를 마칠 때까지 담보권을 설정하지 아니한다.",
        "임차인의 전입신고 다음 날까지 임대인은 매도하지 아니한다.",
        "임대인은 임차인의 주민등록 전입 이전에는 담보권을 설정하지 아니한다.",
    ],
)
def test_j13_does_not_flag_movein_protective_clauses(clause):
    """국토부/HUG 권장 보호 특약은 확인 필요로 뜨면 안 된다 (오탐 금지 원칙)."""
    assert _j13(_judgment_input(present=True, special=[clause])) is RuleStatus.NOT_APPLICABLE


# --- Finding 2: 제외 패턴이 서로 다른 대상을 지닌 정당한 탐지까지 삼키면 안 된다 ------


@pytest.mark.parametrize(
    "clause",
    [
        "매도 시 새 소유자는 본 계약을 승계하지 아니한다. 다만 임차인이 원하는 경우 승계한다.",
        "임차인은 계약갱신요구권을 포기하며 갱신 여부는 임대인과 협의한다.",
    ],
)
def test_j13_flags_mixed_clauses_despite_trailing_benign_phrase(clause):
    assert _j13(_judgment_input(present=True, special=[clause])) is RuleStatus.CHECK_NEEDED


# --- Finding 3: "~하지 않기로 한다" 종결형도 나머지 4종 전부 동일하게 지원해야 한다 ---


@pytest.mark.parametrize(
    "clause",
    [
        "임대인은 보증보험 가입에 협조하지 않기로 한다.",
        "임차인은 계약갱신요구권을 행사하지 않기로 한다.",
    ],
)
def test_j13_flags_hagi_anki_ro_handa_ending_consistently(clause):
    assert _j13(_judgment_input(present=True, special=[clause])) is RuleStatus.CHECK_NEEDED


# --- Finding 4: J13에 연결된 catalog_id만 반환해야 한다 --------------------------


def test_j13_matched_catalog_ids_excludes_non_j13_linked_ids():
    clause = (
        "새로운 임차인의 입주가 완료된 이후 보증금을 반환하며, "
        "임차인은 전입신고를 하지 않기로 한다."
    )
    matched = _j13_matched_catalog_ids([clause])
    assert matched == ("SC-MOVEIN-REPORT-BAN",)
    assert "SC-DEFERRED-REFUND" not in matched
