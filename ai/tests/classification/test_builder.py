"""InputSnapshot → ClassificationInput builder 테스트."""

import json
from pathlib import Path

import pytest

from lease_companion_ai.classification import build_classification_input
from lease_companion_ai.schemas.unified import InputSnapshot

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "data" / "sample" / "fixtures" / "case-001" / "input_snapshot.json"


def _snapshot(
    *,
    schema_version: str = "1.9.0",
    field_values: dict[str, dict] | None = None,
) -> InputSnapshot:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["schema_version"] = schema_version
    payload["contract_context"]["schema_version"] = schema_version
    for field_name, updates in (field_values or {}).items():
        payload["confirmed_fields"]["contract"][field_name].update(updates)
    return InputSnapshot.model_validate(payload)


def test_uses_effective_value_priority_and_stable_single_clause_refs():
    snapshot = _snapshot(
        field_values={
            "deposit_return_clause": {
                "extracted_value": "최초 추출값",
                "normalized_value": "정규화값",
                "user_corrected_value": "사용자 수정값",
                "verification_status": "corrected",
                "confidence": "추출됨",
                "failure_reason": None,
                "issue_code": None,
                "source_evidence": {"page": 2, "text": "보증금 반환 원문"},
            },
            "repair_responsibility_clause": {
                "extracted_value": None,
                "normalized_value": "정규화된 수리 조항",
                "user_corrected_value": None,
            },
        }
    )

    result = build_classification_input(snapshot)

    assert [(clause.clause_ref, clause.text) for clause in result.clauses] == [
        ("deposit_return_clause:0", "사용자 수정값"),
        ("repair_responsibility_clause:0", "정규화된 수리 조항"),
    ]
    assert result.clauses[0].source_evidence.page == 2
    assert result.clauses[0].source_evidence.text == "보증금 반환 원문"


def test_preserves_array_order_and_excludes_blank_clauses():
    snapshot = _snapshot(
        field_values={
            "main_clauses": {
                "extracted_value": ["본문 첫째", "   ", "본문 둘째"],
                "confidence": "추출됨",
                "failure_reason": None,
                "issue_code": None,
            },
            "special_clauses": {
                "extracted_value": ["특약 첫째", "특약 둘째"],
                "confidence": "추출됨",
                "failure_reason": None,
                "issue_code": None,
            },
        }
    )

    result = build_classification_input(snapshot)

    assert [(clause.clause_ref, clause.text) for clause in result.clauses] == [
        ("main_clauses:0", "본문 첫째"),
        ("main_clauses:1", "본문 둘째"),
        ("special_clauses:0", "특약 첫째"),
        ("special_clauses:1", "특약 둘째"),
    ]


def test_excludes_non_clause_contract_fields_and_does_not_mutate_snapshot():
    snapshot = _snapshot(
        field_values={
            "deposit_return_clause": {
                "extracted_value": "계약 종료일에 반환한다.",
                "confidence": "추출됨",
                "failure_reason": None,
                "issue_code": None,
            }
        }
    )
    before = snapshot.model_dump(mode="json")

    first = build_classification_input(snapshot)
    second = build_classification_input(snapshot)

    assert first == second
    assert snapshot.model_dump(mode="json") == before
    assert {clause.source_field.value for clause in first.clauses} == {
        "deposit_return_clause"
    }
    serialized = first.model_dump(mode="json")
    assert "landlord_name" not in serialized
    assert "property_address" not in serialized
    assert "account_holder" not in serialized


@pytest.mark.parametrize("schema_version", ["1.8.0", "1.9.0"])
def test_accepts_v18_and_v19_snapshots(schema_version):
    snapshot = _snapshot(
        schema_version=schema_version,
        field_values={
            "deposit_return_clause": {
                "extracted_value": "계약 종료일에 반환한다.",
                "confidence": "추출됨",
                "failure_reason": None,
                "issue_code": None,
            }
        },
    )

    result = build_classification_input(snapshot)

    assert result.schema_version == schema_version
    assert result.input_snapshot_id == snapshot.input_snapshot_id
    assert result.contract_id == snapshot.contract_id
    assert result.case_id == snapshot.case_id
