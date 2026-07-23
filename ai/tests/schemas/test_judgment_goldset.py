"""J01~J12 입력 경계·허용 상태 goldset 계약 테스트."""

from __future__ import annotations

import json
import csv
from pathlib import Path

import pytest

from lease_companion_ai.schemas.unified import (
    ACTION_TRIGGER_STATUSES,
    ALLOWED_JUDGMENT_STATUSES,
    CLEAN_STATUSES,
    DEFAULT_JUDGMENT_URGENCY,
    JUDGMENT_IDS,
    JUDGMENT_INPUT_SPECS,
    Confidence,
    ContractContext,
    ExtractedField,
    FieldIssueCode,
    JudgmentInput,
    JudgmentResult,
    RuleStatus,
    Urgency,
    VerificationStatus,
)
from lease_companion_ai.rules.judgments import run_judgments

ROOT = Path(__file__).resolve().parents[3]
GOLDSET = ROOT / "data" / "sample" / "expected-results" / "judgment_goldset.jsonl"


def _records() -> list[dict]:
    assert GOLDSET.exists(), f"J goldset이 없습니다: {GOLDSET}"
    return [json.loads(line) for line in GOLDSET.read_text(encoding="utf-8").splitlines() if line]


def _field(name: str, payload: dict) -> ExtractedField:
    value = payload["value"]
    issue = payload.get("issue_code")
    confidence = (
        Confidence.FAILED
        if value is None
        else Confidence.UNCERTAIN
        if issue == FieldIssueCode.AMBIGUOUS.value
        else Confidence.EXTRACTED
    )
    return ExtractedField(
        field_name=name,
        extracted_value=value,
        verification_status=VerificationStatus.CONFIRMED,
        confidence=confidence,
        issue_code=issue,
        failure_reason=(f"goldset:{issue}" if value is None else None),
    )


def _expected_urgency(judgment_id: str, status: RuleStatus) -> Urgency:
    if status in CLEAN_STATUSES:
        return Urgency.REFERENCE
    if status is RuleStatus.CANNOT_CHECK:
        return Urgency.NOT_ANALYZABLE
    return DEFAULT_JUDGMENT_URGENCY[judgment_id]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "judgment_goldset.jsonl에 J13 레코드가 아직 없음(dev goldset 확장은 "
        "docs/decisions/2026-07-23-j13-tenant-protection-restriction.md 후속 과제에서 "
        "처리). J13의 허용 상태 3개(확인 필요 / 적용 제외 / 확인 불가)를 모두 담은 "
        "goldset 블록이 추가되면 이 마커를 지운다."
    ),
)
def test_judgment_goldset_covers_every_allowed_status_with_valid_inputs():
    records = _records()
    assert tuple(record["judgment_id"] for record in records) == JUDGMENT_IDS
    case_ids: set[str] = set()

    for record in records:
        judgment_id = record["judgment_id"]
        spec = JUDGMENT_INPUT_SPECS[judgment_id]
        statuses: set[RuleStatus] = set()
        for case in record["cases"]:
            assert case["case_id"] not in case_ids
            case_ids.add(case["case_id"])
            context_payload = {**record["base_context"], **case.get("context_overrides", {})}
            context = ContractContext(**context_payload)
            contract_fields = {
                name: _field(name, payload)
                for name, payload in case["contract_fields"].items()
            }
            registry_fields = {
                name: _field(name, payload)
                for name, payload in case["registry_fields"].items()
            }
            judgment_input = JudgmentInput(
                input_snapshot_id=f"SNAP-{case['case_id']}",
                contract_id=context.contract_id,
                case_id=case["case_id"],
                judgment_ids=(judgment_id,),
                contract_context=context,
                contract_fields=contract_fields,
                registry_fields=registry_fields,
            )
            assert tuple(judgment_input.contract_fields) == spec.contract_fields
            assert tuple(judgment_input.registry_fields) == spec.registry_fields

            status = RuleStatus(case["expected_status"])
            urgency = Urgency(case["expected_urgency"])
            statuses.add(status)
            assert urgency is _expected_urgency(judgment_id, status)
            JudgmentResult(
                judgment_id=judgment_id,
                judgment_name=record["judgment_name"],
                status=status,
                urgency=urgency,
                triggers_actions=status in ACTION_TRIGGER_STATUSES,
                reason=case["note"],
                limitations="합성 goldset 경계 사례이며 법률 결론이 아닙니다.",
            )

            actual = run_judgments(judgment_input)
            assert len(actual) == 1
            assert actual[0].judgment_id == judgment_id
            assert actual[0].judgment_name == record["judgment_name"]
            assert actual[0].status is status, case["case_id"]
            assert actual[0].urgency is urgency, case["case_id"]
        assert statuses == set(ALLOWED_JUDGMENT_STATUSES[judgment_id])


def test_judgment_metadata_matches_runtime_contract():
    path = ROOT / "data" / "rules" / "judgment_spec.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["judgment_id"] for row in rows] == list(JUDGMENT_IDS)
    for row in rows:
        judgment_id = row["judgment_id"]
        assert set(row["result_status"].split("|")) == {
            status.value for status in ALLOWED_JUDGMENT_STATUSES[judgment_id]
        }
