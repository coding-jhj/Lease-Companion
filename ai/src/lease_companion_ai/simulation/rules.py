"""합성 시나리오를 기존 Python 규칙 엔진 입력으로 변환한다."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from lease_companion_ai.risk_patterns.service import build_damage_patterns_from_results
from lease_companion_ai.rules.judgments import run_judgments
from lease_companion_ai.rules.minimum_mvp import run_rules
from lease_companion_ai.schemas.adapters import rule_result_from_legacy
from lease_companion_ai.schemas.simulation import ScenarioDefinition
from lease_companion_ai.schemas.unified import (
    Confidence,
    ContractContext,
    ContractStage,
    DamagePatternComparison,
    ExtractedField,
    FieldIssueCode,
    JUDGMENT_IDS,
    JUDGMENT_INPUT_SPECS,
    JudgmentInput,
    JudgmentResult,
    RuleResult,
    VerificationStatus,
)


# JudgmentInput의 실전 identity 필드를 만족시키기 위한 메모리 내부 sentinel이다.
# 실제 계약·snapshot 테이블에 저장하거나 외부 practice 결과에 노출하지 않는다.
_PRACTICE_CONTRACT_ID = 2_147_483_647
_PracticeFieldValue = str | int | bool | list[str] | dict[str, str] | date | None


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
    return tuple(
        rule_result_from_legacy(result) for result in run_rules(contract, registry)
    )


def _linked_judgment_ids(scenario: ScenarioDefinition) -> tuple[str, ...]:
    linked = {
        judgment_id
        for signal in scenario.hidden_confirmation_signals
        for judgment_id in signal.linked_judgment_ids
    }
    return tuple(judgment_id for judgment_id in JUDGMENT_IDS if judgment_id in linked)


def _contract_stage(scenario: ScenarioDefinition) -> ContractStage:
    if scenario.synthetic_contract.signed:
        return ContractStage.AFTER_CONTRACT
    if scenario.contract_stage == ContractStage.BEFORE_SIGNING.value:
        return ContractStage.BEFORE_SIGNING
    return ContractStage.BEFORE_DEPOSIT


def _field(
    field_name: str,
    value: _PracticeFieldValue,
) -> ExtractedField:
    if isinstance(value, date):
        value = value.isoformat()
    if value is None or value == [] or value == {}:
        return ExtractedField(
            field_name=field_name,
            extracted_value=None,
            verification_status=VerificationStatus.CONFIRMED,
            confidence=Confidence.FAILED,
            issue_code=FieldIssueCode.NOT_STATED,
            failure_reason="합성 시나리오에 값이 제시되지 않았습니다.",
        )
    return ExtractedField(
        field_name=field_name,
        extracted_value=value,
        verification_status=VerificationStatus.CONFIRMED,
        confidence=Confidence.EXTRACTED,
    )


def build_practice_judgment_input(scenario: ScenarioDefinition) -> JudgmentInput:
    """합성 사실만으로 canonical J 입력을 만들며 실제 계약 snapshot은 만들지 않는다."""

    judgment_ids = _linked_judgment_ids(scenario)
    if not judgment_ids:
        raise ValueError("연습 시나리오에 연결된 J 판정이 없습니다.")

    contract_names: list[str] = []
    registry_names: list[str] = []
    for judgment_id in judgment_ids:
        spec = JUDGMENT_INPUT_SPECS[judgment_id]
        for name in spec.contract_fields:
            if name not in contract_names:
                contract_names.append(name)
        for name in spec.registry_fields:
            if name not in registry_names:
                registry_names.append(name)

    synthetic = scenario.synthetic_contract
    contract_fields = {
        name: _field(name, getattr(synthetic, name)) for name in contract_names
    }
    registry_values: dict[str, _PracticeFieldValue] = {
        "property_address": synthetic.registry_property_address,
        "owner_names": synthetic.owner_names,
        "is_joint_ownership": synthetic.is_joint_ownership,
        "owner_shares": synthetic.owner_shares,
    }
    registry_fields = {
        name: _field(name, registry_values[name]) for name in registry_names
    }
    allowed_candidate_fields = set(contract_names)
    candidates = [
        candidate
        for candidate in scenario.classification_candidates
        if candidate.clause_ref.partition(":")[0] in allowed_candidate_fields
    ]
    context = ContractContext(
        contract_id=_PRACTICE_CONTRACT_ID,
        contract_type=synthetic.contract_type,
        contract_stage=_contract_stage(scenario),
        deposit_paid=synthetic.deposit_paid,
        signed=synthetic.signed,
        move_in_date=synthetic.move_in_date,
        balance_payment_date=synthetic.balance_payment_date,
        is_proxy_contract=synthetic.is_proxy_contract,
    )
    return JudgmentInput(
        input_snapshot_id=(
            f"PRACTICE-SNAPSHOT-{scenario.scenario_id}-{scenario.scenario_version}"
        ),
        contract_id=_PRACTICE_CONTRACT_ID,
        case_id=scenario.scenario_id,
        judgment_ids=judgment_ids,
        contract_context=context,
        contract_fields=contract_fields,
        registry_fields=registry_fields,
        classification_candidates=candidates,
    )


def run_practice_judgments(
    scenario: ScenarioDefinition,
) -> tuple[JudgmentResult, ...]:
    """fixture에 명시적으로 연결된 J 판정만 canonical 엔진으로 실행한다."""

    return tuple(run_judgments(build_practice_judgment_input(scenario)))


def run_practice_damage_patterns(
    scenario: ScenarioDefinition,
    rule_results: Sequence[RuleResult] | None = None,
    judgment_results: Sequence[JudgmentResult] | None = None,
) -> tuple[DamagePatternComparison, ...]:
    """실제 분석 실행 ID 없이 합성 R/J 결과로 DP01~DP08을 구성한다."""

    rules = tuple(rule_results) if rule_results is not None else run_practice_rules(scenario)
    judgments = (
        tuple(judgment_results)
        if judgment_results is not None
        else run_practice_judgments(scenario)
    )
    return tuple(build_damage_patterns_from_results(rules, judgments))


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


def link_actions_to_judgments(
    scenario: ScenarioDefinition,
    judgment_results: Sequence[JudgmentResult],
) -> dict[str, tuple[JudgmentResult, ...]]:
    """action→signal→judgment 참조만 따라가며 판정 결과는 변경하지 않는다."""

    signal_judgments = {
        signal.signal_id: tuple(signal.linked_judgment_ids)
        for signal in scenario.hidden_confirmation_signals
    }
    result_by_id = {result.judgment_id: result for result in judgment_results}
    links: dict[str, tuple[JudgmentResult, ...]] = {}
    for action in scenario.target_actions:
        linked_ids: list[str] = []
        for signal_id in action.linked_signal_ids:
            for judgment_id in signal_judgments[signal_id]:
                if judgment_id not in linked_ids:
                    linked_ids.append(judgment_id)
        links[action.action_id] = tuple(
            result_by_id[judgment_id]
            for judgment_id in linked_ids
            if judgment_id in result_by_id
        )
    return links
