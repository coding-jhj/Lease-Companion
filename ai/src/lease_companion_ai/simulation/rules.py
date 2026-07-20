"""합성 시나리오를 기존 Python 규칙 엔진 입력으로 변환한다."""

from __future__ import annotations

from collections.abc import Sequence

from lease_companion_ai.rules.minimum_mvp import run_rules
from lease_companion_ai.schemas.minimum_mvp import RuleResult
from lease_companion_ai.schemas.simulation import ScenarioDefinition


def run_practice_rules(scenario: ScenarioDefinition) -> tuple[RuleResult, ...]:
    """실제 계약과 분리된 합성 사실에 R01~R24를 결정적으로 실행한다."""

    synthetic = scenario.synthetic_contract
    contract = synthetic.model_dump(mode="python")
    signal_ids = {
        signal.signal_id for signal in scenario.hidden_confirmation_signals
    }
    contract.update(
        {
            "deposit_return_condition": (
                "불명확"
                if "SIG-RETURN-AMBIGUOUS" in signal_ids
                else "확인 필요"
            ),
            "repair_responsibility": "확인 필요",
        }
    )
    registry = {
        "property_address": synthetic.registry_property_address,
        "owner_names": list(synthetic.owner_names),
        "mortgage_present": synthetic.mortgage_present,
        "issue_date": synthetic.registry_issue_date,
        # 시나리오에 없는 권리 상태를 '없음'으로 추측하지 않는다.
        "seizure_present": None,
        "provisional_seizure_present": None,
        "trust_present": None,
        "senior_claim_amount": None,
    }
    return tuple(run_rules(contract, registry))


def link_actions_to_rules(
    scenario: ScenarioDefinition,
    rule_results: Sequence[RuleResult],
) -> dict[str, tuple[RuleResult, ...]]:
    """action→signal→rule 참조만 따라가며 규칙 결과 자체는 변경하지 않는다."""

    signal_rules = {
        signal.signal_id: tuple(signal.linked_rule_ids)
        for signal in scenario.hidden_confirmation_signals
    }
    result_by_id = {result.rule_id: result for result in rule_results}
    links: dict[str, tuple[RuleResult, ...]] = {}
    for action in scenario.target_actions:
        linked_ids: list[str] = []
        for signal_id in action.linked_signal_ids:
            for rule_id in signal_rules[signal_id]:
                if rule_id not in linked_ids:
                    linked_ids.append(rule_id)
        links[action.action_id] = tuple(
            result_by_id[rule_id]
            for rule_id in linked_ids
            if rule_id in result_by_id
        )
    return links
