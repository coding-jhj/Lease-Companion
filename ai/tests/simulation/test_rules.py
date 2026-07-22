from __future__ import annotations

from pathlib import Path

import pytest

from lease_companion_ai.schemas.unified import DamagePatternStatus, RuleStatus
from lease_companion_ai.simulation.models import load_practice_assets
from lease_companion_ai.simulation.rules import (
    build_practice_judgment_input,
    link_actions_to_judgments,
    link_actions_to_rules,
    run_practice_damage_patterns,
    run_practice_judgments,
    run_practice_rules,
)


ROOT = Path(__file__).resolve().parents[3]
SCENARIO_ROOT = ROOT / "data" / "sample" / "practice-scenarios"


def _scenario(scenario_id: str):
    fixture_dir = SCENARIO_ROOT / scenario_id
    scenario, _ = load_practice_assets(
        fixture_dir / "scenario.json",
        fixture_dir / "answer-key.json",
    )
    return scenario


@pytest.mark.parametrize(
    "scenario_id,expected_judgments,pattern_id,pattern_status",
    [
        (
            "PRACTICE-DEFERRED-REFUND-001",
            {"J10": RuleStatus.CHECK_NEEDED},
            "DP08",
            DamagePatternStatus.RELATED_SIGNAL,
        ),
        (
            "PRACTICE-THIRD-PARTY-PAYMENT-001",
            {"J05": RuleStatus.MISMATCH},
            "DP02",
            DamagePatternStatus.RELATED_SIGNAL,
        ),
        (
            "PRACTICE-PROXY-AUTHORITY-001",
            {
                "J01": RuleStatus.CHECK_NEEDED,
                "J04": RuleStatus.CHECK_NEEDED,
            },
            None,
            None,
        ),
    ],
)
def test_three_scenarios_run_canonical_r_j_dp_golden_matrix(
    scenario_id,
    expected_judgments,
    pattern_id,
    pattern_status,
):
    scenario = _scenario(scenario_id)

    rules = run_practice_rules(scenario)
    judgments = run_practice_judgments(scenario)
    patterns = run_practice_damage_patterns(scenario, rules, judgments)

    assert len(rules) == 24
    assert {item.judgment_id: item.status for item in judgments} == expected_judgments
    assert [item.pattern_id for item in patterns] == [
        f"DP{index:02d}" for index in range(1, 9)
    ]
    if pattern_id is not None:
        by_pattern = {item.pattern_id: item for item in patterns}
        assert by_pattern[pattern_id].status is pattern_status


def test_deferred_refund_comparison_remains_clear_when_not_linked_to_new_tenant():
    scenario = _scenario("PRACTICE-DEFERRED-REFUND-001")
    synthetic = scenario.synthetic_contract.model_copy(
        update={
            "deposit_return_clause": (
                "신규 임차인 입주와 관계없이 계약 종료일에 보증금을 반환한다."
            )
        }
    )
    candidate = scenario.classification_candidates[0].model_copy(
        update={
            "condition_candidates": [
                "신규 임차인 입주와 관계없이 계약 종료일"
            ]
        }
    )
    comparison = scenario.model_copy(
        update={
            "synthetic_contract": synthetic,
            "classification_candidates": [candidate],
        }
    )

    judgments = run_practice_judgments(comparison)
    patterns = run_practice_damage_patterns(comparison)

    assert judgments[0].status is RuleStatus.CLEAR
    assert {item.pattern_id: item for item in patterns}["DP08"].status is (
        DamagePatternStatus.NO_SIGNAL_IN_SUBMITTED_DOCS
    )


def test_third_party_account_becomes_check_needed_in_proxy_context():
    scenario = _scenario("PRACTICE-THIRD-PARTY-PAYMENT-001")
    proxy_contract = scenario.synthetic_contract.model_copy(
        update={"is_proxy_contract": True}
    )
    comparison = scenario.model_copy(update={"synthetic_contract": proxy_contract})

    judgments = run_practice_judgments(comparison)

    assert judgments[0].judgment_id == "J05"
    assert judgments[0].status is RuleStatus.CHECK_NEEDED


def test_non_proxy_comparison_makes_j04_not_applicable():
    scenario = _scenario("PRACTICE-PROXY-AUTHORITY-001")
    direct_contract = scenario.synthetic_contract.model_copy(
        update={
            "is_proxy_contract": False,
            "agent_name": None,
            "agent_relationship": None,
            "proxy_authority_documents": [],
        }
    )
    comparison = scenario.model_copy(update={"synthetic_contract": direct_contract})

    judgments = {
        item.judgment_id: item for item in run_practice_judgments(comparison)
    }

    assert judgments["J01"].status is RuleStatus.MATCH
    assert judgments["J04"].status is RuleStatus.NOT_APPLICABLE


def test_proxy_authority_actions_do_not_invent_r04_links():
    scenario = _scenario("PRACTICE-PROXY-AUTHORITY-001")
    rules = run_practice_rules(scenario)
    judgments = run_practice_judgments(scenario)

    rule_links = link_actions_to_rules(scenario, rules)
    judgment_links = link_actions_to_judgments(scenario, judgments)

    assert all(not linked for linked in rule_links.values())
    assert all(
        [item.judgment_id for item in linked] == ["J01", "J04"]
        for linked in judgment_links.values()
    )
    assert all(
        item.rule_id != "R04"
        for linked in rule_links.values()
        for item in linked
    )


def test_practice_judgment_adapter_uses_only_fixture_linked_judgments():
    scenario = _scenario("PRACTICE-DEFERRED-REFUND-001")

    judgment_input = build_practice_judgment_input(scenario)

    assert judgment_input.judgment_ids == ("J10",)
    assert set(judgment_input.contract_fields) == {"deposit_return_clause"}
    assert judgment_input.registry_fields == {}
    assert judgment_input.case_id == scenario.scenario_id
