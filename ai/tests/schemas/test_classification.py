"""Canonical classification v1.9 입력·결과 계약 테스트."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from lease_companion_ai.schemas import (
    ClassificationInput,
    ClassificationResult,
    ClauseCandidate,
    ClauseInput,
    validate_classification_result_for_input,
)
from lease_companion_ai.schemas.unified import InputSnapshot, SCHEMA_VERSION


FIXTURE_DIR = Path("data/sample/fixtures/case-001")


def _input(**overrides) -> ClassificationInput:
    payload = {
        "input_snapshot_id": "SNAP-1",
        "contract_id": 1,
        "clauses": [
            ClauseInput(
                clause_ref="deposit_return_clause:0",
                source_field="deposit_return_clause",
                ordinal=0,
                text="계약 종료일에 보증금을 반환한다.",
            )
        ],
    }
    payload.update(overrides)
    return ClassificationInput(**payload)


def _candidate(clause_ref: str = "deposit_return_clause:0") -> ClauseCandidate:
    return ClauseCandidate(
        clause_ref=clause_ref,
        clause_type="deposit_return",
        clarity_candidate="명확",
        responsible_party_candidate="임대인",
        condition_candidates=["계약 종료일"],
        review_required=False,
    )


def _result(**overrides) -> ClassificationResult:
    payload = {
        "input_snapshot_id": "SNAP-1",
        "contract_id": 1,
        "provider_model": "gemini/gemini-3.5-flash",
        "prompt_version": "classification-v1",
        "classification_method": "provider",
        "candidates": [_candidate()],
    }
    payload.update(overrides)
    return ClassificationResult(**payload)


def test_v19_input_snapshot_fixture_and_v18_read_compatibility():
    payload = json.loads((FIXTURE_DIR / "input_snapshot.json").read_text(encoding="utf-8"))
    snapshot = InputSnapshot.model_validate(payload)
    assert snapshot.schema_version == "1.9.0"

    payload["schema_version"] = "1.8.0"
    payload["contract_context"]["schema_version"] = "1.8.0"
    assert InputSnapshot.model_validate(payload).schema_version == "1.8.0"


def test_v19_classification_round_trip_and_public_exports():
    classification_input = _input()
    result = _result()

    assert SCHEMA_VERSION == "1.9.0"
    assert ClassificationInput.model_validate_json(
        classification_input.model_dump_json()
    ) == classification_input
    restored = ClassificationResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert validate_classification_result_for_input(classification_input, restored) is restored


@pytest.mark.parametrize("field_name", ["input_snapshot_id", "contract_id", "schema_version"])
def test_result_identifiers_must_match_input(field_name):
    classification_input = _input()
    bad_values = {
        "input_snapshot_id": "SNAP-OTHER",
        "contract_id": 2,
        "schema_version": "1.8.0",
    }
    result = _result(**{field_name: bad_values[field_name]})

    with pytest.raises(ValueError, match=field_name):
        validate_classification_result_for_input(classification_input, result)


def test_rejects_duplicate_candidate_for_clause_ref():
    with pytest.raises(ValidationError, match="중복 clause_ref"):
        _result(candidates=[_candidate(), _candidate()])


def test_rejects_unknown_candidate_clause_ref():
    with pytest.raises(ValueError, match="알 수 없는 clause_ref"):
        validate_classification_result_for_input(
            _input(),
            _result(candidates=[_candidate("main_clauses:0")]),
        )


def test_rejects_personal_information_field():
    with pytest.raises(ValidationError, match="landlord_name"):
        ClassificationInput(
            input_snapshot_id="SNAP-1",
            contract_id=1,
            clauses=[],
            landlord_name="홍길동",
        )


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("status", "확인 필요"),
        ("urgency", "계약 전 확인"),
        ("reason", "최종 판정 이유"),
    ],
)
def test_rejects_rule_status_urgency_and_final_reason(field_name, value):
    with pytest.raises(ValidationError, match=field_name):
        ClassificationResult(
            input_snapshot_id="SNAP-1",
            contract_id=1,
            provider_model="gemini/gemini-3.5-flash",
            prompt_version="classification-v1",
            classification_method="provider",
            candidates=[],
            **{field_name: value},
        )


def test_provider_and_safe_fallback_provenance_are_distinct():
    provider = _result()
    fallback = _result(
        classification_method="safe_fallback",
        fallback_reason_code="provider_unavailable",
        candidates=[],
    )
    assert provider.fallback_reason_code is None
    assert fallback.fallback_reason_code == "provider_unavailable"

    with pytest.raises(ValidationError, match="fallback_reason_code"):
        _result(fallback_reason_code="provider_unavailable")
    with pytest.raises(ValidationError, match="fallback_reason_code"):
        _result(classification_method="safe_fallback", candidates=[])


def test_clause_ref_must_match_source_field_and_ordinal():
    with pytest.raises(ValidationError, match="source_field:ordinal"):
        ClauseInput(
            clause_ref="main_clauses:1",
            source_field="main_clauses",
            ordinal=0,
            text="본문 조항",
        )
