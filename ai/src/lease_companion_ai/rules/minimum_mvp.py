"""최소 MVP R01~R10 결정론적 규칙 엔진."""

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
    }


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
    }.get(rule_id, "추가 확인이 필요한 사실 플래그입니다.")


def _presentation(
    rule_id: str, status: str, definition: dict[str, str]
) -> tuple[str, str, str | None, list[str]]:
    """상태 종류별 (시급도, 이유, 질문, 행동). 반환: 판정 상태를 단정으로 오표시하지 않도록 분리."""
    if status in _CLEAN_STATUSES:
        return "참고", _clean_reason(rule_id), None, []
    if status == "확인 불가":
        # 정보가 없어 비교·판정을 못 한 경우 — 발동(불일치 등) 문구를 붙이지 않는다.
        return (
            "분석 불가",
            "이 항목을 판정할 정보를 문서에서 확인하지 못해 비교할 수 없습니다.",
            None,
            ["필요한 문서·값(예: 등기사항증명서, 해당 항목)을 확인한 뒤 다시 분석하세요."],
        )
    return (
        definition["urgency"],
        definition["report_reason"],
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
        urgency, reason, question, actions = _presentation(rule_id, status, definition)
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
