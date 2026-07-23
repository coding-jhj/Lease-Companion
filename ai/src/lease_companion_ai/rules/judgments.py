"""J01~J13 결정론적 판정 엔진.

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
    ClarityCandidate,
    ClauseCandidate,
    ClauseType,
    DEFAULT_JUDGMENT_URGENCY,
    ContractType,
    ExtractedField,
    FieldIssueCode,
    JudgmentInput,
    JudgmentResult,
    ResponsiblePartyCandidate,
    RuleStatus,
    Urgency,
)
from lease_companion_ai.special_clauses import match_special_clauses


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


def _has_issue(judgment_input: JudgmentInput, names: tuple[str, ...], *issues: FieldIssueCode) -> bool:
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
    return RuleStatus.CHECK_NEEDED if _value(data, "is_joint_ownership") is True else RuleStatus.NOT_APPLICABLE


def _j04(data: JudgmentInput) -> RuleStatus:
    proxy = data.contract_context.is_proxy_contract
    if proxy is False:
        return RuleStatus.NOT_APPLICABLE
    if proxy is None:
        return RuleStatus.CANNOT_CHECK
    names = ("agent_name", "agent_relationship", "proxy_authority_documents")
    if _is_missing(data, names) and _has_issue(data, names, FieldIssueCode.UNREADABLE, FieldIssueCode.PARSE_FAILED):
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
        and (data.contract_context.move_in_date is None or move_in == data.contract_context.move_in_date)
        and (
            data.contract_context.balance_payment_date is None or balance == data.contract_context.balance_payment_date
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


def _candidate(data: JudgmentInput, clause_ref: str) -> ClauseCandidate | None:
    return next(
        (candidate for candidate in data.classification_candidates if candidate.clause_ref == clause_ref),
        None,
    )


def _raw_clause_state(data: JudgmentInput, field_name: str) -> RuleStatus | None:
    field = data.contract_fields[field_name]
    if field.effective_value is None:
        return RuleStatus.NOT_STATED if field.issue_code is FieldIssueCode.NOT_STATED else RuleStatus.CHECK_NEEDED
    return None


def _candidate_clarity(candidate: ClauseCandidate) -> RuleStatus:
    if candidate.review_required:
        return RuleStatus.CHECK_NEEDED
    if candidate.clarity_candidate is ClarityCandidate.UNCLEAR:
        return RuleStatus.UNCLEAR
    if candidate.clarity_candidate is ClarityCandidate.CHECK_NEEDED:
        return RuleStatus.CHECK_NEEDED
    return RuleStatus.CLEAR


_RETURN_CONTEXT = re.compile(r"보증금.{0,20}(?:반환|지급|돌려|정산)|(?:반환|지급|돌려|정산).{0,20}보증금")
_RETURN_INDEPENDENCE = re.compile(r"(?:관계\s*없이|무관하게|상관\s*없이|연동하지\s*않)")
_TENANT_REQUEST_EXCEPTION = re.compile(r"임차인.{0,20}(?:요청|희망).{0,20}(?:경우|때)")
_DEFERRED_RETURN_EVENTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("신규 임차인의 입주", re.compile(r"(?:신규|새|다음|후속)\s*(?:임차인|세입자)")),
    ("주택 매각", re.compile(r"(?:주택|임차주택|목적물|부동산).{0,12}(?:매각|매매|처분)")),
    ("임대인의 자금 사정", re.compile(r"(?:임대인|집주인).{0,15}(?:자금\s*사정|자금|보증금\s*마련)")),
)


def _deferred_return_event(text: str | None) -> str | None:
    if (
        not text
        or not _RETURN_CONTEXT.search(text)
        or _RETURN_INDEPENDENCE.search(text)
        or _TENANT_REQUEST_EXCEPTION.search(text)
    ):
        return None
    return next(
        (label for label, pattern in _DEFERRED_RETURN_EVENTS if pattern.search(text)),
        None,
    )


def _has_deferred_return_text(text: str | None) -> bool:
    return _deferred_return_event(text) is not None


def _has_deferred_return_condition(candidate: ClauseCandidate, raw_clause: str | None = None) -> bool:
    """Detect an explicit dependency on finding or admitting a later tenant.

    This is a narrow confirmation signal, not a legal-validity judgment.  Clauses
    that explicitly say the refund is independent of a later tenant are excluded.
    """

    texts = [*candidate.condition_candidates]
    if raw_clause:
        texts.append(raw_clause)
    return any(_has_deferred_return_text(text) for text in texts)


def _deferred_return_condition_event(candidate: ClauseCandidate | None, raw_clause: str | None) -> str | None:
    texts = [raw_clause] if raw_clause else []
    if candidate is not None:
        texts.extend(candidate.condition_candidates)
    return next(
        (event for text in texts if (event := _deferred_return_event(text)) is not None),
        None,
    )


def _j10(data: JudgmentInput) -> RuleStatus:
    raw_state = _raw_clause_state(data, "deposit_return_clause")
    if raw_state is not None:
        return raw_state
    raw_value = data.contract_fields["deposit_return_clause"].effective_value
    raw_clause = raw_value if isinstance(raw_value, str) else None
    # 사용자가 확인한 원문에 좁고 명시적인 반환 연동 조건이 있으면 provider
    # 후보가 없더라도 확인 신호를 보존한다. 법적 효력·위험도를 판정하지 않는다.
    if _has_deferred_return_text(raw_clause):
        return RuleStatus.CHECK_NEEDED
    candidate = _candidate(data, "deposit_return_clause:0")
    if candidate is None or candidate.clause_type is not ClauseType.DEPOSIT_RETURN:
        return RuleStatus.CHECK_NEEDED
    clarity = _candidate_clarity(candidate)
    if clarity is not RuleStatus.CLEAR:
        return clarity
    if _has_deferred_return_condition(candidate, raw_clause):
        return RuleStatus.CHECK_NEEDED
    return RuleStatus.CLEAR if candidate.condition_candidates else RuleStatus.UNCLEAR


def _j11(data: JudgmentInput) -> RuleStatus:
    raw_state = _raw_clause_state(data, "repair_responsibility_clause")
    if raw_state is not None:
        return raw_state
    candidate = _candidate(data, "repair_responsibility_clause:0")
    if candidate is None or candidate.clause_type is not ClauseType.REPAIR_RESTORATION:
        return RuleStatus.CHECK_NEEDED
    clarity = _candidate_clarity(candidate)
    if clarity is not RuleStatus.CLEAR:
        return clarity
    return (
        RuleStatus.UNCLEAR
        if candidate.responsible_party_candidate is ResponsiblePartyCandidate.UNSPECIFIED
        else RuleStatus.CLEAR
    )


def _expected_clause_refs(field_name: str, clauses: list[str]) -> list[str]:
    return [f"{field_name}:{ordinal}" for ordinal, clause in enumerate(clause for clause in clauses if clause.strip())]


def _candidate_facts(
    candidates: list[ClauseCandidate],
) -> dict[ClauseType, dict[str, set[str]]]:
    grouped: dict[ClauseType, dict[str, set[str]]] = {}
    for candidate in candidates:
        facts = grouped.setdefault(candidate.clause_type, {"conditions": set(), "parties": set()})
        facts["conditions"].update(candidate.condition_candidates)
        if candidate.responsible_party_candidate is not ResponsiblePartyCandidate.UNSPECIFIED:
            facts["parties"].add(candidate.responsible_party_candidate.value)
    return grouped


_DATE_PATTERN = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
_MONEY_PATTERN = re.compile(r"(?<!\d)\d[\d,]*\s*원")


def _legacy_clause_values(clauses: list[str], marker: str, pattern: re.Pattern[str]) -> set[str]:
    return {match.replace(" ", "") for clause in clauses if marker in clause for match in pattern.findall(clause)}


def _legacy_structured_conflict(main: list[str], special: list[str]) -> bool:
    for marker in ("계약 종료일", "계약 시작일", "보증금", "월세", "계약금", "잔금"):
        pattern = _DATE_PATTERN if "일" in marker else _MONEY_PATTERN
        main_values = _legacy_clause_values(main, marker, pattern)
        special_values = _legacy_clause_values(special, marker, pattern)
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
    if not isinstance(main, list) or not isinstance(special, list):
        return RuleStatus.CHECK_NEEDED
    if _legacy_structured_conflict(main, special):
        return RuleStatus.POSSIBLE_CONFLICT
    if data.schema_version == "1.8.0" and not data.classification_candidates:
        normalized_special = " ".join(special)
        if "본문과 동일" in normalized_special or main == special:
            return RuleStatus.CLEAR
        return RuleStatus.CHECK_NEEDED

    main_refs = _expected_clause_refs("main_clauses", main)
    special_refs = _expected_clause_refs("special_clauses", special)
    candidates_by_ref = {candidate.clause_ref: candidate for candidate in data.classification_candidates}
    expected_refs = main_refs + special_refs
    if any(clause_ref not in candidates_by_ref for clause_ref in expected_refs):
        return RuleStatus.CHECK_NEEDED

    main_candidates = [candidates_by_ref[clause_ref] for clause_ref in main_refs]
    special_candidates = [candidates_by_ref[clause_ref] for clause_ref in special_refs]
    all_candidates = main_candidates + special_candidates
    if any(
        candidate.review_required or candidate.clarity_candidate is not ClarityCandidate.CLEAR
        for candidate in all_candidates
    ):
        return RuleStatus.CHECK_NEEDED

    main_facts = _candidate_facts(main_candidates)
    special_facts = _candidate_facts(special_candidates)
    for clause_type in main_facts.keys() & special_facts.keys():
        for fact_name in ("conditions", "parties"):
            left = main_facts[clause_type][fact_name]
            right = special_facts[clause_type][fact_name]
            if not left and not right:
                continue
            if not left or not right:
                return RuleStatus.CHECK_NEEDED
            if left != right:
                return RuleStatus.POSSIBLE_CONFLICT
    return RuleStatus.CLEAR


_J13_JUDGMENT_ID = "J13"


def _j13_matched_catalog_ids(clauses: list[str]) -> tuple[str, ...]:
    """J13에 연결된 카탈로그 항목만 세어 반환한다.

    기존 독소조항 6종(SC-DEFERRED-REFUND 등)이 매칭돼도 J13에는 영향을 주지 않는다.
    그쪽은 각자 연결된 R08·R09·R10·R18·J09~J12가 담당한다.
    """
    return tuple(
        catalog_id
        for candidate in match_special_clauses(clauses)
        if _J13_JUDGMENT_ID in candidate.related_judgment_ids
        for catalog_id in candidate.catalog_ids
    )


def _j13(data: JudgmentInput) -> RuleStatus:
    names = ("special_clauses",)
    if _has_issue(data, names, FieldIssueCode.AMBIGUOUS, FieldIssueCode.PARSE_FAILED):
        return RuleStatus.CANNOT_CHECK
    present = _value(data, "special_clauses_present")
    special = _value(data, "special_clauses")
    if special is None:
        # present=False면 특약이 없는 것이고, 그 외에는 판독 실패다.
        return RuleStatus.NOT_APPLICABLE if present is False else RuleStatus.CANNOT_CHECK
    if not isinstance(special, list):
        return RuleStatus.CANNOT_CHECK
    clauses = [clause for clause in special if isinstance(clause, str) and clause.strip()]
    if not clauses:
        # present=False면 특약이 없다는 신호와 일치하므로 적용 제외.
        # 그 외(present=True인데 원문 목록이 비거나 공백뿐)는 신호가 어긋난 것이므로 확인 불가.
        return RuleStatus.NOT_APPLICABLE if present is False else RuleStatus.CANNOT_CHECK
    if _j13_matched_catalog_ids(clauses):
        return RuleStatus.CHECK_NEEDED
    return RuleStatus.NOT_APPLICABLE


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
    "J13": _j13,
}


def _result(judgment_id: str, status: RuleStatus, judgment_input: JudgmentInput) -> JudgmentResult:
    definition = _definitions()[judgment_id]
    clean = status in CLEAN_STATUSES
    urgency = (
        Urgency.REFERENCE
        if clean
        else Urgency.NOT_ANALYZABLE
        if status is RuleStatus.CANNOT_CHECK
        else DEFAULT_JUDGMENT_URGENCY[judgment_id]
    )
    candidate = _candidate(judgment_input, "deposit_return_clause:0") if judgment_id == "J10" else None
    raw_return_value = (
        judgment_input.contract_fields["deposit_return_clause"].effective_value if judgment_id == "J10" else None
    )
    raw_return_clause = raw_return_value if isinstance(raw_return_value, str) else None
    deferred_event = _deferred_return_condition_event(candidate, raw_return_clause)
    if judgment_id == "J10" and deferred_event is not None:
        reason = f"보증금 반환이 {deferred_event}에 연동된 조건이 확인되어 " "반환 조건의 수정 여부를 확인해야 합니다."
    elif judgment_id == "J11":
        raw_repair_clause = judgment_input.contract_fields["repair_responsibility_clause"].effective_value
        raw_text = raw_repair_clause if isinstance(raw_repair_clause, str) else ""
        has_repair = bool(re.search(r"수리|수선|고장|보일러|설비", raw_text))
        has_restoration = bool(re.search(r"원상복구|원상회복|퇴거|통상\s*손모", raw_text))
        topic = (
            "계약 존속 중 수리와 계약 종료 시 원상복구"
            if has_repair and has_restoration
            else "계약 종료 시 원상복구"
            if has_restoration
            else "계약 존속 중 수리"
            if has_repair
            else "수리·원상복구"
        )
        reason = f"{topic} 책임의 주체와 범위를 확인한 결과: {status.value}."
    elif status is RuleStatus.CANNOT_CHECK:
        reason = f"{definition['judgment_name']} 판정에 필요한 값을 확인할 수 없습니다."
    else:
        reason = f"{definition['report_reason']} 결과: {status.value}."
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
        _result(
            judgment_id,
            _EVALUATORS[judgment_id](judgment_input),
            judgment_input,
        )
        for judgment_id in judgment_input.judgment_ids
    ]
