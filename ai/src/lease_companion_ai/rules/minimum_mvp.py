"""최소 MVP R01~R10 결정론적 규칙 엔진."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from lease_companion_ai.normalization.core import normalize_address, normalize_name
from lease_companion_ai.schemas.minimum_mvp import EvidenceSource, RuleResult


_CLEAN_STATUSES = {"일치", "명확", "적용 제외"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _read_csv(name: str) -> list[dict[str, str]]:
    path = _repo_root() / "data" / "rules" / name
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _evidence_catalog() -> dict[str, EvidenceSource]:
    catalog: dict[str, EvidenceSource] = {}
    for row in _read_csv("source_inventory.csv"):
        raw_url = row["source_url"].strip()
        url = raw_url if raw_url.startswith(("http://", "https://")) else None
        catalog[row["source_id"]] = EvidenceSource(
            source_id=row["source_id"],
            title=row["title"],
            institution=row["institution"],
            summary=row["summary"],
            source_url=url,
        )
    return catalog


def _status_map(contract: dict[str, Any], registry: dict[str, Any]) -> dict[str, str]:
    landlord = normalize_name(contract.get("landlord_name"))
    owners = [normalize_name(value) for value in registry.get("owner_names") or []]
    contract_address = normalize_address(contract.get("property_address"))
    registry_address = normalize_address(registry.get("property_address"))
    account_holder = normalize_name(contract.get("account_holder"))

    return {
        "R01": "확인 불가" if not landlord or not owners else "일치" if landlord in owners else "불일치",
        "R02": "확인 불가" if not contract_address or not registry_address else "일치" if contract_address == registry_address else "불일치",
        "R03": "확인 불가" if not registry else "확인 필요" if registry.get("mortgage_present") else "적용 제외",
        "R04": "확인 불가" if not registry else "확인 필요" if registry.get("seizure_present") or registry.get("provisional_seizure_present") else "적용 제외",
        "R05": "확인 불가" if not registry else "확인 필요" if registry.get("trust_present") else "적용 제외",
        "R06": "확인 불가" if not landlord else "확인 필요" if not account_holder else "일치" if landlord == account_holder else "불일치",
        "R07": "확인 불가" if not registry else "확인 필요" if registry.get("issue_date") else "미기재",
        "R08": contract.get("deposit_return_condition") or "확인 필요",
        "R09": contract.get("repair_responsibility") or "확인 필요",
        "R10": "명확" if contract.get("rights_change_clause_present") else "미기재",
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


def run_rules(contract: dict[str, Any], registry: dict[str, Any]) -> list[RuleResult]:
    definitions = _read_csv("rule_spec.csv")
    catalog = _evidence_catalog()
    statuses = _status_map(contract, registry)
    results: list[RuleResult] = []

    for definition in definitions:
        rule_id = definition["rule_id"]
        status = statuses[rule_id]
        is_clean = status in _CLEAN_STATUSES
        evidence = [
            catalog[source_id]
            for source_id in definition["official_source_ids"].split(";")
            if source_id in catalog
        ]
        results.append(
            RuleResult(
                rule_id=rule_id,
                rule_name=definition["rule_name"],
                judgment_id=definition["judgment_id"] or None,
                status=status,
                urgency="참고" if is_clean else definition["urgency"],
                reason=_clean_reason(rule_id) if is_clean else definition["report_reason"],
                question=None if is_clean else definition["question_template"],
                recommended_actions=[] if is_clean else [definition["action_template"]],
                evidence_sources=evidence,
                limitations=definition["limitations"],
            )
        )
    return results
