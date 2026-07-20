"""MVP R01~R24 결정론적 규칙 엔진과 단계적 확인 규칙."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from lease_companion_ai.normalization.core import normalize_address, normalize_name
from lease_companion_ai.schemas.minimum_mvp import RuleResult


_CLEAN_STATUSES = {"일치", "명확", "적용 제외"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _read_csv(name: str) -> list[dict[str, str]]:
    path = _repo_root() / "data" / "rules" / name
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _status_map(contract: dict[str, Any], registry: dict[str, Any]) -> dict[str, str]:
    landlord = normalize_name(contract.get("landlord_name"))
    owners = [normalize_name(value) for value in registry.get("owner_names") or []]
    contract_address = normalize_address(contract.get("property_address"))
    registry_address = normalize_address(registry.get("property_address"))
    account_holder = normalize_name(contract.get("account_holder"))

    # 등기 존재/기재 플래그는 tri-state: True=있음, False=(읽고) 없음, None=판독불가·미확인.
    # None → "확인 불가"로 일관 처리(판독불가 등기부를 "이상 없음"으로 오판하지 않도록).
    mortgage = registry.get("mortgage_present")
    seizure = registry.get("seizure_present")
    provisional = registry.get("provisional_seizure_present")
    trust = registry.get("trust_present")
    issue_date = registry.get("issue_date")
    rights_change = contract.get("rights_change_clause_present")
    deposit = contract.get("deposit")
    housing_value = contract.get("estimated_housing_value")
    senior_claim_amount = registry.get("senior_claim_amount")
    is_proxy_contract = contract.get("is_proxy_contract")
    proxy_documents = contract.get("proxy_authority_documents")
    building_use = contract.get("building_use")
    violation_building = contract.get("violation_building")
    guarantee_eligible = contract.get("guarantee_eligibility_confirmed")
    sublease_authority = contract.get("lessor_sublease_authority_confirmed")
    management_fee_present = contract.get("management_fee_present")
    management_fee = contract.get("management_fee")
    management_fee_items = contract.get("management_fee_items")
    return {
        "R01": "확인 불가" if not landlord or not owners else "일치" if landlord in owners else "불일치",
        "R02": "확인 불가" if not contract_address or not registry_address else "일치" if contract_address == registry_address else "불일치",
        "R03": "확인 불가" if not registry else "확인 필요" if mortgage else "적용 제외" if mortgage is False else "확인 불가",
        "R04": "확인 불가" if not registry else "확인 필요" if seizure or provisional else "적용 제외" if seizure is False and provisional is False else "확인 불가",
        "R05": "확인 불가" if not registry else "확인 필요" if trust else "적용 제외" if trust is False else "확인 불가",
        "R06": "확인 불가" if not landlord else "확인 필요" if not account_holder else "일치" if landlord == account_holder else "불일치",
        "R07": "확인 불가" if not registry else "확인 필요" if issue_date else "확인 불가",
        "R08": contract.get("deposit_return_condition") or "확인 필요",
        "R09": contract.get("repair_responsibility") or "확인 필요",
        "R10": "명확" if rights_change else "미기재" if rights_change is False else "확인 불가",
        # 비율·합계는 계산 결과를 제공하되 임의의 안전 임계값으로 판정하지 않는다.
        "R11": (
            "확인 필요"
            if isinstance(deposit, int)
            and isinstance(housing_value, int)
            and housing_value > 0
            else "확인 불가"
        ),
        "R12": (
            "확인 필요"
            if isinstance(senior_claim_amount, int) and senior_claim_amount >= 0
            else "확인 불가"
        ),
        "R13": (
            "적용 제외" if is_proxy_contract is False
            else "확인 불가" if is_proxy_contract is None
            else "명확" if proxy_documents
            else "확인 필요"
        ),
        "R14": (
            "확인 불가" if not building_use or violation_building is None
            else "확인 필요" if violation_building
            else "명확"
        ),
        "R15": "확인 불가" if guarantee_eligible is None else "명확" if guarantee_eligible else "확인 필요",
        "R16": "확인 필요",
        "R17": "확인 불가" if sublease_authority is None else "명확" if sublease_authority else "확인 필요",
        "R18": (
            "확인 불가" if management_fee_present is None
            else "적용 제외" if management_fee_present is False
            else "명확" if isinstance(management_fee, int) and bool(management_fee_items)
            else "불명확"
        ),
        "R19": "명확" if rights_change else "미기재" if rights_change is False else "확인 불가",
        # 아래 셋은 외부 조회 계약이 생길 때까지 자동 판정을 금지한다.
        "R20": "확인 불가",
        "R21": "확인 불가",
        "R22": "확인 불가",
        # 신뢰할 수 있는 단일 문서 입력만으로 자동 판정할 수 없어 질문형으로 제공한다.
        "R23": "확인 필요",
        "R24": "확인 필요",
    }


def _reason_override(
    rule_id: str, contract: dict[str, Any], registry: dict[str, Any]
) -> str | None:
    if rule_id == "R11":
        deposit = contract.get("deposit")
        housing_value = contract.get("estimated_housing_value")
        if isinstance(deposit, int) and isinstance(housing_value, int) and housing_value > 0:
            ratio = deposit / housing_value * 100
            return (
                f"확인된 보증금은 {deposit:,}원, 입력된 주택가치는 {housing_value:,}원으로 "
                f"비율은 {ratio:.1f}%입니다. 이 비율만으로 계약의 안전 여부를 판단하지 않습니다."
            )
    if rule_id == "R12":
        amount = registry.get("senior_claim_amount")
        if isinstance(amount, int) and amount >= 0:
            return (
                f"확인된 선순위 권리·채권 합계 입력값은 {amount:,}원입니다. "
                "실제 우선순위와 회수 가능성은 최신 등기 및 관련 자료로 별도 확인해야 합니다."
            )
    return None


def _clean_reason(rule_id: str) -> str:
    return {
        "R01": "계약서 임대인과 등기상 소유자 이름이 일치합니다.",
        "R02": "계약서와 등기사항증명서의 목적물 주소가 일치합니다.",
        "R03": "근저당권 관련 활성 기재가 탐지되지 않았습니다.",
        "R04": "압류·가압류 관련 활성 기재가 탐지되지 않았습니다.",
        "R05": "신탁 관련 활성 기재가 탐지되지 않았습니다.",
        "R06": "계약서 임대인과 입금 계좌 명의가 일치합니다.",
        "R08": "보증금 반환 시점·조건이 문구에 구체적으로 기재되어 있습니다.",
        "R09": "수리·원상복구 책임 주체와 범위가 문구에 기재되어 있습니다.",
        "R10": "계약 후 권리변동을 제한하는 특약 문구가 확인됩니다.",
        "R13": "대리계약에 필요한 권한 확인 서류가 입력되어 있습니다.",
        "R14": "입력된 건축물 용도와 위반건축물 여부를 확인했습니다.",
        "R15": "보증기관의 현재 가입 요건을 확인한 것으로 입력되어 있습니다.",
        "R17": "임대·전대 권한을 확인한 것으로 입력되어 있습니다.",
        "R18": "관리비 금액과 포함 항목이 함께 기재되어 있습니다.",
        "R19": "계약 전후 권리변동을 제한하는 특약 문구가 확인됩니다.",
    }.get(rule_id, "추가 확인이 필요한 사실 플래그입니다.")


def _presentation(
    rule_id: str, status: str, definition: dict[str, str], reason_override: str | None = None
) -> tuple[str, str, str | None, list[str]]:
    """상태 종류별 (시급도, 이유, 질문, 행동). 반환: 판정 상태를 단정으로 오표시하지 않도록 분리."""
    if status == "적용 제외" and rule_id == "R13":
        return "참고", "대리계약이 아닌 것으로 입력되어 이 항목은 적용하지 않습니다.", None, []
    if status == "적용 제외" and rule_id == "R18":
        return "참고", "관리비가 없는 것으로 입력되어 이 항목은 적용하지 않습니다.", None, []
    if status in _CLEAN_STATUSES:
        return "참고", _clean_reason(rule_id), None, []
    if status == "확인 불가":
        # 정보가 없어 비교·판정을 못 한 경우 — 발동(불일치 등) 문구를 붙이지 않는다.
        if int(rule_id[1:]) >= 11:
            return (
                "분석 불가",
                "현재 입력 또는 외부 연동이 없어 이 항목을 자동 판정할 수 없습니다.",
                definition["question_template"] or None,
                [definition["action_template"]] if definition["action_template"] else [],
            )
        return (
            "분석 불가",
            "이 항목을 판정할 정보를 문서에서 확인하지 못해 비교할 수 없습니다.",
            None,
            ["필요한 문서·값(예: 등기사항증명서, 해당 항목)을 확인한 뒤 다시 분석하세요."],
        )
    return (
        definition["urgency"],
        reason_override or definition["report_reason"],
        definition["question_template"],
        [definition["action_template"]],
    )


def run_rules(contract: dict[str, Any], registry: dict[str, Any]) -> list[RuleResult]:
    definitions = _read_csv("rule_spec.csv")
    statuses = _status_map(contract, registry)
    results: list[RuleResult] = []

    for definition in definitions:
        rule_id = definition["rule_id"]
        status = statuses[rule_id]
        urgency, reason, question, actions = _presentation(
            rule_id,
            status,
            definition,
            _reason_override(rule_id, contract, registry),
        )
        results.append(
            RuleResult(
                rule_id=rule_id,
                rule_name=definition["rule_name"],
                judgment_id=definition["judgment_id"] or None,
                status=status,
                urgency=urgency,
                reason=reason,
                question=question,
                recommended_actions=actions,
                # 공식 근거는 규칙 판정 뒤 RAG가 실제 검색한 결과만 연결한다.
                evidence_sources=[],
                limitations=definition["limitations"],
            )
        )
    return results
