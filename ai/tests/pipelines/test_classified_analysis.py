from __future__ import annotations

import json
from pathlib import Path

from lease_companion_ai.classification.service import ClassificationService
from lease_companion_ai.pipelines.classified_analysis import (
    analyze_with_classification,
)
from lease_companion_ai.providers.classification import (
    CLASSIFICATION_PROMPT_VERSION,
    FakeClassificationProvider,
)
from lease_companion_ai.schemas.unified import (
    ClassificationMethod,
    ClassificationResult,
    ClauseCandidate,
    InputSnapshot,
    RuleStatus,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "data" / "sample" / "fixtures" / "case-001" / "input_snapshot.json"


def _snapshot() -> InputSnapshot:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["schema_version"] = "1.9.0"
    payload["contract_context"]["schema_version"] = "1.9.0"
    contract = payload["confirmed_fields"]["contract"]
    contract["deposit_return_clause"].update(
        extracted_value="임대인은 계약 종료일에 보증금을 반환한다.",
        confidence="추출됨",
        issue_code=None,
        failure_reason=None,
    )
    return InputSnapshot.model_validate(payload)


def _provider_result(snapshot: InputSnapshot) -> ClassificationResult:
    return ClassificationResult(
        schema_version=snapshot.schema_version,
        input_snapshot_id=snapshot.input_snapshot_id,
        contract_id=snapshot.contract_id,
        provider_model="fake-classification-v1",
        prompt_version=CLASSIFICATION_PROMPT_VERSION,
        classification_method=ClassificationMethod.PROVIDER,
        candidates=[
            ClauseCandidate(
                clause_ref="deposit_return_clause:0",
                clause_type="deposit_return",
                clarity_candidate="명확",
                responsible_party_candidate="임대인",
                condition_candidates=["계약 종료일"],
                review_required=False,
            )
        ],
    )


def _status(analysis, judgment_id: str) -> RuleStatus:
    return next(
        result.status for result in analysis.judgments if result.judgment_id == judgment_id
    )


def test_provider_candidates_are_passed_to_judgment_analysis() -> None:
    snapshot = _snapshot()
    expected = _provider_result(snapshot)
    provider = FakeClassificationProvider({snapshot.input_snapshot_id: expected})

    classification, analysis = analyze_with_classification(
        snapshot,
        analysis_run_id="RUN-CLASSIFIED",
        classification_service=ClassificationService(provider),
    )

    assert classification == expected
    assert _status(analysis, "J10") is RuleStatus.CLEAR
    assert analysis.input_snapshot_id == classification.input_snapshot_id
    assert analysis.contract_id == classification.contract_id


def test_safe_fallback_keeps_analysis_available_without_candidates() -> None:
    snapshot = _snapshot()

    classification, analysis = analyze_with_classification(
        snapshot,
        analysis_run_id="RUN-FALLBACK",
        classification_service=ClassificationService(),
    )

    assert classification.classification_method is ClassificationMethod.SAFE_FALLBACK
    assert classification.candidates == []
    assert _status(analysis, "J10") is RuleStatus.CHECK_NEEDED
    assert [result.rule_id for result in analysis.results] == [
        f"R{index:02d}" for index in range(1, 25)
    ]
