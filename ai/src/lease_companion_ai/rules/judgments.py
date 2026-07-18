"""J01~J12 결정론적 판정 엔진.

사용자가 확인한 ``JudgmentInput``만 소비한다. LLM·RAG는 이 모듈이 정한
``RuleStatus``와 ``Urgency``를 변경하지 않는다.
"""

from __future__ import annotations

import csv
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Callable

from lease_companion_ai.normalization.core import normalize_address, normalize_name
from lease_companion_ai.schemas.unified import (
    ACTION_TRIGGER_STATUSES,
    CLEAN_STATUSES,
    DEFAULT_JUDGMENT_URGENCY,
    ContractType,
    ExtractedField,
    FieldIssueCode,
    JudgmentInput,
    JudgmentResult,
    RuleStatus,
    Urgency,
)

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@lru_cache(maxsize=1)
def _definitions() -> dict[str, dict[str, str]]:
    path = _repo_root() / "data" / "rules" / "judgment_spec.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["judgment_id"]: row for row in rows}


def _field(judgment_input: JudgmentInput, name: str) -> ExtractedField:
    return judgment_input.contract_fields.get(name) or judgment_input.registry_fields[name]


def _value(judgment_input: JudgmentInput, name: str):
    return _field(judgment_input, name).effective_value


def _has_issue(
    judgment_input: JudgmentInput, names: tuple[str, ...], *issues: FieldIssueCode
) -> bool:
    return any(_field(judgment_input, name).issue_code in issues for name in names)


def _is_missing(judgment_input: JudgmentInput, names: tuple[str, ...]) -> bool:
    return any(_value(judgment_input, name) is None for name in names)


def _j01(data: JudgmentInput) -> RuleStatus:
    if data.contract_context.is_proxy_contract is True:
        return RuleStatus.CHECK_NEEDED
    names = ("landlord_name", "owner_names")
    if _has_issue(data, names, FieldIssueCode.AMBIGUOUS):
        return RuleStatus.CHECK_NEEDED
    if _is_missing(data, names):
        return RuleStatus.CANNOT_CHECK
    landlord = normalize_name(_value(data, "landlord_name"))
    owners = [normalize_name(name) for name in _value(data, "owner_names")]
    return RuleStatus.MATCH if landlord in owners else RuleStatus.MISMATCH


def _j02(data: JudgmentInput) -> RuleStatus:
    contract = data.contract_fields["property_address"]
    registry = data.registry_fields["property_address"]
    if FieldIssueCode.AMBIGUOUS in {contract.issue_code, registry.issue_code}:
        return RuleStatus.CHECK_NEEDED
    if contract.effective_value is None or registry.effective_value is None:
        return RuleStatus.CANNOT_CHECK
    left = normalize_address(str(contract.effective_value))
    right = normalize_address(str(registry.effective_value))
    return RuleStatus.MATCH if left == right else RuleStatus.MISMATCH


def _j03(data: JudgmentInput) -> RuleStatus:
    names = ("owner_names", "is_joint_ownership", "owner_shares")
    if _has_issue(data, names, FieldIssueCode.AMBIGUOUS):
        return RuleStatus.CHECK_NEEDED
    if _is_missing(data, names):
        return RuleStatus.CANNOT_CHECK
    return (
        RuleStatus.CHECK_NEEDED
        if _value(data, "is_joint_ownership") is True
        else RuleStatus.NOT_APPLICABLE
    )


def _j04(data: JudgmentInput) -> RuleStatus:
    proxy = data.contract_context.is_proxy_contract
    if proxy is False:
        return RuleStatus.NOT_APPLICABLE
    if proxy is None:
        return RuleStatus.CANNOT_CHECK
    names = ("agent_name", "agent_relationship", "proxy_authority_documents")
    if _is_missing(data, names) and _has_issue(
        data, names, FieldIssueCode.UNREADABLE, FieldIssueCode.PARSE_FAILED
    ):
        return RuleStatus.CANNOT_CHECK
    return RuleStatus.CHECK_NEEDED


def _j05(data: JudgmentInput) -> RuleStatus:
    names = ("account_holder", "landlord_name", "owner_names")
    if data.contract_context.is_proxy_contract is True:
        return RuleStatus.CHECK_NEEDED
    if _has_issue(data, names, FieldIssueCode.AMBIGUOUS):
        return RuleStatus.CHECK_NEEDED
    if _is_missing(data, names):
        if _has_issue(data, names, FieldIssueCode.NOT_STATED):
            return RuleStatus.CHECK_NEEDED
        return RuleStatus.CANNOT_CHECK
    account = normalize_name(_value(data, "account_holder"))
    landlord = normalize_name(_value(data, "landlord_name"))
    owners = [normalize_name(name) for name in _value(data, "owner_names")]
    return RuleStatus.MATCH if account == landlord and account in owners else RuleStatus.MISMATCH


def _amount_fields(contract_type: ContractType) -> tuple[str, ...]:
    if contract_type is ContractType.JEONSE:
        return ("deposit", "contract_payment", "balance_payment")
    if contract_type is ContractType.DEPOSIT_MONTHLY:
        return ("deposit", "monthly_rent", "contract_payment", "balance_payment")
    return ("monthly_rent",)


def _j06(data: JudgmentInput) -> RuleStatus:
    names = _amount_fields(data.contract_context.contract_type)
    if _has_issue(data, names, FieldIssueCode.AMBIGUOUS, FieldIssueCode.PARSE_FAILED):
        return RuleStatus.CHECK_NEEDED
    if _is_missing(data, names):
        if _has_issue(data, names, FieldIssueCode.NOT_STATED):
            return RuleStatus.NOT_STATED
        return RuleStatus.CHECK_NEEDED
    if data.contract_context.contract_type is ContractType.MONTHLY:
        return RuleStatus.NOT_APPLICABLE
    return RuleStatus.CLEAR


def _j07(data: JudgmentInput) -> RuleStatus:
    amounts = _amount_fields(data.contract_context.contract_type)
    pairs = tuple((name, f"{name}_korean_amount") for name in amounts)
    names = tuple(name for pair in pairs for name in pair)
    if _has_issue(data, names, FieldIssueCode.PARSE_FAILED, FieldIssueCode.UNREADABLE):
        return RuleStatus.CANNOT_CHECK
    if _is_missing(data, names) or _has_issue(data, names, FieldIssueCode.AMBIGUOUS):
        return RuleStatus.CHECK_NEEDED
    return (
        RuleStatus.MATCH
        if all(_value(data, numeric) == _value(data, korean) for numeric, korean in pairs)
        else RuleStatus.MISMATCH
    )


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _j08(data: JudgmentInput) -> RuleStatus:
    names = (
        "contract_payment_date",
        "balance_payment_date",
        "move_in_date",
        "start_date",
        "end_date",
    )
    if _has_issue(data, names, FieldIssueCode.AMBIGUOUS, FieldIssueCode.PARSE_FAILED):
        return RuleStatus.CHECK_NEEDED
    if _is_missing(data, names):
        if _has_issue(data, names, FieldIssueCode.NOT_STATED):
            return RuleStatus.NOT_STATED
        return RuleStatus.CHECK_NEEDED
    parsed = {name: _parse_date(_value(data, name)) for name in names}
    if any(value is None for value in parsed.values()):
        return RuleStatus.CHECK_NEEDED
    contract_payment = parsed["contract_payment_date"]
    balance = parsed["balance_payment_date"]
    move_in = parsed["move_in_date"]
    start = parsed["start_date"]
    end = parsed["end_date"]
    assert contract_payment is not None
    assert balance is not None
    assert move_in is not None
    assert start is not None
    assert end is not None
    consistent = (
        contract_payment <= balance <= move_in
        and move_in == start
        and start < end
        and (
            data.contract_context.move_in_date is None
            or move_in == data.contract_context.move_in_date
        )
        and (
            data.contract_context.balance_payment_date is None
            or balance == data.contract_context.balance_payment_date
        )
    )
    return RuleStatus.MATCH if consistent else RuleStatus.MISMATCH


def _j09(data: JudgmentInput) -> RuleStatus:
    present = _value(data, "management_fee_present")
    if present is False:
        return RuleStatus.NOT_APPLICABLE
    if present is None:
        return RuleStatus.CHECK_NEEDED
    details = ("management_fee", "management_fee_items")
    missing_count = sum(_value(data, name) is None for name in details)
    if missing_count == len(details) and _has_issue(data, details, FieldIssueCode.NOT_STATED):
        return RuleStatus.NOT_STATED
    if missing_count or _has_issue(data, details, FieldIssueCode.AMBIGUOUS):
        return RuleStatus.UNCLEAR
    return RuleStatus.CLEAR


def _clarity_status(data: JudgmentInput, field_name: str) -> RuleStatus:
    mapping = {
        "명확": RuleStatus.CLEAR,
        "불명확": RuleStatus.UNCLEAR,
        "미기재": RuleStatus.NOT_STATED,
        "확인 필요": RuleStatus.CHECK_NEEDED,
    }
    value = _value(data, field_name)
    return mapping.get(value, RuleStatus.CHECK_NEEDED)


def _j10(data: JudgmentInput) -> RuleStatus:
    return _clarity_status(data, "deposit_return_condition")


def _j11(data: JudgmentInput) -> RuleStatus:
    return _clarity_status(data, "repair_responsibility")


_DATE_PATTERN = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
_MONEY_PATTERN = re.compile(r"(?<!\d)\d[\d,]*\s*원")


def _clause_values(clauses: list[str], marker: str, pattern: re.Pattern[str]) -> set[str]:
    return {
        match.replace(" ", "")
        for clause in clauses
        if marker in clause
        for match in pattern.findall(clause)
    }


def _has_structured_conflict(main: list[str], special: list[str]) -> bool:
    for marker in ("계약 종료일", "계약 시작일", "보증금", "월세", "계약금", "잔금"):
        pattern = _DATE_PATTERN if "일" in marker else _MONEY_PATTERN
        main_values = _clause_values(main, marker, pattern)
        special_values = _clause_values(special, marker, pattern)
        if main_values and special_values and main_values != special_values:
            return True
    for marker in ("수리", "원상복구"):
        main_text = " ".join(clause for clause in main if marker in clause)
        special_text = " ".join(clause for clause in special if marker in clause)
        if main_text and special_text:
            main_party = {party for party in ("임대인", "임차인") if party in main_text}
            special_party = {party for party in ("임대인", "임차인") if party in special_text}
            if main_party and special_party and main_party != special_party:
                return True
    return False


def _j12(data: JudgmentInput) -> RuleStatus:
    if _value(data, "special_clauses_present") is False:
        return RuleStatus.NOT_APPLICABLE
    names = ("main_clauses", "special_clauses")
    if _is_missing(data, names) or _has_issue(data, names, FieldIssueCode.AMBIGUOUS):
        return RuleStatus.CHECK_NEEDED
    main = _value(data, "main_clauses")
    special = _value(data, "special_clauses")
    if _has_structured_conflict(main, special):
        return RuleStatus.POSSIBLE_CONFLICT
    normalized_special = " ".join(special)
    if "본문과 동일" in normalized_special or main == special:
        return RuleStatus.CLEAR
    return RuleStatus.CHECK_NEEDED


_EVALUATORS: dict[str, Callable[[JudgmentInput], RuleStatus]] = {
    "J01": _j01,
    "J02": _j02,
    "J03": _j03,
    "J04": _j04,
    "J05": _j05,
    "J06": _j06,
    "J07": _j07,
    "J08": _j08,
    "J09": _j09,
    "J10": _j10,
    "J11": _j11,
    "J12": _j12,
}


def _result(judgment_id: str, status: RuleStatus) -> JudgmentResult:
    definition = _definitions()[judgment_id]
    clean = status in CLEAN_STATUSES
    urgency = (
        Urgency.REFERENCE
        if clean
        else Urgency.NOT_ANALYZABLE
        if status is RuleStatus.CANNOT_CHECK
        else DEFAULT_JUDGMENT_URGENCY[judgment_id]
    )
    reason = (
        f"{definition['report_reason']} 결과: {status.value}."
        if status is not RuleStatus.CANNOT_CHECK
        else f"{definition['judgment_name']} 판정에 필요한 값을 확인할 수 없습니다."
    )
    return JudgmentResult(
        judgment_id=judgment_id,
        judgment_name=definition["judgment_name"],
        status=status,
        urgency=urgency,
        triggers_actions=status in ACTION_TRIGGER_STATUSES,
        reason=reason,
        question=None if clean else definition["question_template"],
        recommended_actions=[] if clean else [definition["action_template"]],
        evidence_sources=[],
        limitations=definition["limitations"],
    )


def run_judgments(judgment_input: JudgmentInput) -> list[JudgmentResult]:
    """요청된 canonical 순서의 J 판정을 실행한다."""

    return [
        _result(judgment_id, _EVALUATORS[judgment_id](judgment_input))
        for judgment_id in judgment_input.judgment_ids
    ]
