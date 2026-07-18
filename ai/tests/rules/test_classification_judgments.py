from __future__ import annotations

import json
from pathlib import Path

import pytest

from lease_companion_ai.rules.judgments import run_judgments
from lease_companion_ai.schemas.adapters import analyze_snapshot
from lease_companion_ai.schemas.unified import (
    JUDGMENT_INPUT_SPECS,
    REQUIRED_CONTRACT_FIELDS,
    ClassificationMethod,
    ClassificationResult,
    ClauseCandidate,
    DocumentExtraction,
    InputSnapshot,
    RuleStatus,
    build_judgment_input,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "data" / "sample" / "fixtures" / "case-001"


def _snapshot(
    *,
    schema_version: str = "1.9.0",
    field_values: dict[str, object | None] | None = None,
) -> InputSnapshot:
    payload = json.loads((FIXTURE_DIR / "input_snapshot.json").read_text(encoding="utf-8"))
    payload["schema_version"] = schema_version
    payload["contract_context"]["schema_version"] = schema_version
    fields = payload["confirmed_fields"]["contract"]
    for legacy_name in ("deposit_return_condition", "repair_responsibility"):
        fields[legacy_name].update(
            {
                "extracted_value": None,
                "normalized_value": None,
                "user_corrected_value": None,
                "confidence": "실패",
                "issue_code": "not_stated",
                "failure_reason": "v1.9 deprecated field",
            }
        )
    for field_name, value in (field_values or {}).items():
        field = fields[field_name]
        field.update(
            {
                "extracted_value": value,
                "normalized_value": None,
                "user_corrected_value": None,
                "confidence": "추출됨" if value is not None else "실패",
                "issue_code": None if value is not None else "not_stated",
                "failure_reason": None if value is not None else "문서에 기재되지 않음",
            }
        )
    return InputSnapshot.model_validate(payload)


def _candidate(
    clause_ref: str,
    *,
    clause_type: str,
    clarity: str = "명확",
    responsible_party: str = "미지정",
    conditions: list[str] | None = None,
    review_required: bool = False,
) -> ClauseCandidate:
    return ClauseCandidate(
        clause_ref=clause_ref,
        clause_type=clause_type,
        clarity_candidate=clarity,
        responsible_party_candidate=responsible_party,
        condition_candidates=conditions or [],
        review_required=review_required,
    )


def _classification(
    snapshot: InputSnapshot,
    candidates: list[ClauseCandidate],
) -> ClassificationResult:
    return ClassificationResult(
        schema_version=snapshot.schema_version,
        input_snapshot_id=snapshot.input_snapshot_id,
        contract_id=snapshot.contract_id,
        provider_model="fake-classification-v1",
        prompt_version="classification-v1",
        classification_method=ClassificationMethod.PROVIDER,
        candidates=candidates,
    )


def _judgment_status(
    snapshot: InputSnapshot,
    judgment_id: str,
    candidates: list[ClauseCandidate],
) -> RuleStatus:
    result = _classification(snapshot, candidates)
    judgment_input = build_judgment_input(
        snapshot,
        judgment_ids=(judgment_id,),
        classification_result=result,
    )
    return run_judgments(judgment_input)[0].status


def test_v19_contract_no_longer_requires_deprecated_candidate_fields() -> None:
    payload = json.loads(
        (FIXTURE_DIR / "contract_extraction.json").read_text(encoding="utf-8")
    )
    payload["schema_version"] = "1.9.0"
    payload["fields"].pop("deposit_return_condition")
    payload["fields"].pop("repair_responsibility")

    document = DocumentExtraction.model_validate(payload)

    assert "deposit_return_condition" not in REQUIRED_CONTRACT_FIELDS
    assert "repair_responsibility" not in REQUIRED_CONTRACT_FIELDS
    assert "deposit_return_condition" not in document.fields
    assert "repair_responsibility" not in document.fields


def test_v18_snapshot_remains_readable_with_raw_only_judgment_inputs() -> None:
    snapshot = InputSnapshot.model_validate_json(
        (FIXTURE_DIR / "input_snapshot.json").read_text(encoding="utf-8")
    )

    j10 = build_judgment_input(snapshot, judgment_ids=("J10",))
    j11 = build_judgment_input(snapshot, judgment_ids=("J11",))

    assert set(j10.contract_fields) == {"deposit_return_clause"}
    assert set(j11.contract_fields) == {"repair_responsibility_clause"}
    assert j10.classification_candidates == []
    assert j11.classification_candidates == []


def test_j10_uses_return_type_clarity_and_conditions() -> None:
    snapshot = _snapshot(
        field_values={"deposit_return_clause": "계약 종료일에 보증금을 반환한다."}
    )

    clear = _judgment_status(
        snapshot,
        "J10",
        [
            _candidate(
                "deposit_return_clause:0",
                clause_type="deposit_return",
                conditions=["계약 종료일"],
            )
        ],
    )
    missing_conditions = _judgment_status(
        snapshot,
        "J10",
        [_candidate("deposit_return_clause:0", clause_type="deposit_return")],
    )

    assert clear is RuleStatus.CLEAR
    assert missing_conditions is RuleStatus.UNCLEAR


def test_j11_requires_repair_type_clarity_and_responsible_party() -> None:
    snapshot = _snapshot(
        field_values={"repair_responsibility_clause": "수리는 임대인이 부담한다."}
    )

    clear = _judgment_status(
        snapshot,
        "J11",
        [
            _candidate(
                "repair_responsibility_clause:0",
                clause_type="repair_restoration",
                responsible_party="임대인",
            )
        ],
    )
    unspecified = _judgment_status(
        snapshot,
        "J11",
        [
            _candidate(
                "repair_responsibility_clause:0",
                clause_type="repair_restoration",
            )
        ],
    )

    assert clear is RuleStatus.CLEAR
    assert unspecified is RuleStatus.UNCLEAR


@pytest.mark.parametrize("judgment_id", ["J10", "J11", "J12"])
def test_missing_classification_candidate_returns_safe_check_needed(
    judgment_id: str,
) -> None:
    snapshot = _snapshot(
        field_values={
            "deposit_return_clause": "계약 종료일에 반환한다.",
            "repair_responsibility_clause": "수리는 임대인이 부담한다.",
            "main_clauses": ["보증금은 계약 종료일에 반환한다."],
            "special_clauses_present": True,
            "special_clauses": ["보증금은 퇴거 완료일에 반환한다."],
        }
    )

    assert _judgment_status(snapshot, judgment_id, []) is RuleStatus.CHECK_NEEDED


def test_j10_and_j11_return_not_stated_when_raw_clause_is_absent() -> None:
    snapshot = _snapshot(
        field_values={
            "deposit_return_clause": None,
            "repair_responsibility_clause": None,
        }
    )

    assert _judgment_status(snapshot, "J10", []) is RuleStatus.NOT_STATED
    assert _judgment_status(snapshot, "J11", []) is RuleStatus.NOT_STATED


def test_j12_compares_main_and_special_candidate_types_and_conditions() -> None:
    snapshot = _snapshot(
        field_values={
            "main_clauses": ["보증금은 계약 종료일에 반환한다."],
            "special_clauses_present": True,
            "special_clauses": ["보증금은 퇴거 완료일에 반환한다."],
        }
    )

    conflict = _judgment_status(
        snapshot,
        "J12",
        [
            _candidate(
                "main_clauses:0",
                clause_type="deposit_return",
                conditions=["계약 종료일"],
            ),
            _candidate(
                "special_clauses:0",
                clause_type="deposit_return",
                conditions=["퇴거 완료일"],
            ),
        ],
    )
    matching = _judgment_status(
        snapshot,
        "J12",
        [
            _candidate(
                "main_clauses:0",
                clause_type="deposit_return",
                conditions=["계약 종료일"],
            ),
            _candidate(
                "special_clauses:0",
                clause_type="deposit_return",
                conditions=["계약 종료일"],
            ),
        ],
    )

    assert conflict is RuleStatus.POSSIBLE_CONFLICT
    assert matching is RuleStatus.CLEAR


def test_classification_result_identifiers_must_match_snapshot() -> None:
    snapshot = _snapshot()
    mismatched = _classification(snapshot, []).model_copy(
        update={"input_snapshot_id": "SNAP-OTHER"}
    )

    with pytest.raises(ValueError, match="input_snapshot_id"):
        build_judgment_input(
            snapshot,
            judgment_ids=("J10",),
            classification_result=mismatched,
        )


def test_classification_candidates_never_change_legacy_rule_results() -> None:
    snapshot = _snapshot(
        field_values={
            "deposit_return_clause": "계약 종료일에 보증금을 반환한다.",
            "repair_responsibility_clause": "수리는 임대인이 부담한다.",
        }
    )
    clear = _classification(
        snapshot,
        [
            _candidate(
                "deposit_return_clause:0",
                clause_type="deposit_return",
                conditions=["계약 종료일"],
            )
        ],
    )
    unclear = _classification(
        snapshot,
        [
            _candidate(
                "deposit_return_clause:0",
                clause_type="deposit_return",
                clarity="불명확",
            )
        ],
    )

    clear_analysis = analyze_snapshot(
        snapshot,
        analysis_run_id="RUN-CLEAR",
        classification_result=clear,
    )
    unclear_analysis = analyze_snapshot(
        snapshot,
        analysis_run_id="RUN-UNCLEAR",
        classification_result=unclear,
    )

    assert [result.status for result in clear_analysis.results] == [
        result.status for result in unclear_analysis.results
    ]
    assert JUDGMENT_INPUT_SPECS["J10"].contract_fields == (
        "deposit_return_clause",
    )
    assert JUDGMENT_INPUT_SPECS["J11"].contract_fields == (
        "repair_responsibility_clause",
    )
