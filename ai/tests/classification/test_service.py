from __future__ import annotations

import json
from pathlib import Path

from lease_companion_ai.classification import (
    ClassificationFallbackReason,
    ClassificationService,
    build_classification_input,
)
from lease_companion_ai.providers.classification import (
    CLASSIFICATION_PROMPT_VERSION,
    FakeClassificationProvider,
)
from lease_companion_ai.schemas import (
    ClassificationInput,
    ClassificationMethod,
    ClassificationResult,
    ClauseCandidate,
    validate_classification_result_for_input,
)
from lease_companion_ai.schemas.unified import InputSnapshot

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "data" / "sample" / "fixtures" / "case-001" / "input_snapshot.json"


def _snapshot() -> InputSnapshot:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["schema_version"] = "1.9.0"
    payload["contract_context"]["schema_version"] = "1.9.0"
    return InputSnapshot.model_validate(payload)


def _provider_result(
    snapshot: InputSnapshot,
    *,
    candidates: list[ClauseCandidate] | None = None,
) -> ClassificationResult:
    return ClassificationResult(
        schema_version=snapshot.schema_version,
        input_snapshot_id=snapshot.input_snapshot_id,
        contract_id=snapshot.contract_id,
        provider_model="fake-classification-v1",
        prompt_version=CLASSIFICATION_PROMPT_VERSION,
        classification_method=ClassificationMethod.PROVIDER,
        candidates=candidates or [],
    )


def _assert_fallback(
    result: ClassificationResult,
    snapshot: InputSnapshot,
    reason: ClassificationFallbackReason,
) -> None:
    assert result.schema_version == snapshot.schema_version
    assert result.input_snapshot_id == snapshot.input_snapshot_id
    assert result.contract_id == snapshot.contract_id
    assert result.classification_method is ClassificationMethod.SAFE_FALLBACK
    assert result.fallback_reason_code == reason.value
    assert result.prompt_version == CLASSIFICATION_PROMPT_VERSION
    assert result.candidates == []
    classification_input = build_classification_input(snapshot)
    assert validate_classification_result_for_input(classification_input, result) is result


class NonValidatingProvider:
    model_name = "non-validating-provider"

    def __init__(self, result: ClassificationResult) -> None:
        self.result = result

    def classify(self, _: ClassificationInput) -> ClassificationResult:
        return self.result


class RawFailingProvider:
    model_name = "raw-failing-provider"

    def __init__(self, message: str) -> None:
        self.message = message

    def classify(self, _: ClassificationInput) -> ClassificationResult:
        raise RuntimeError(self.message)


def test_returns_provider_result_after_service_validation() -> None:
    snapshot = _snapshot()
    expected = _provider_result(snapshot)
    provider = FakeClassificationProvider({snapshot.input_snapshot_id: expected})

    result = ClassificationService(provider).classify(snapshot)

    assert result == expected
    assert len(provider.calls) == 1


def test_missing_provider_returns_unavailable_fallback() -> None:
    snapshot = _snapshot()

    result = ClassificationService().classify(snapshot)

    _assert_fallback(
        result,
        snapshot,
        ClassificationFallbackReason.PROVIDER_UNAVAILABLE,
    )
    assert result.provider_model == "unconfigured"


def test_provider_call_failure_returns_provider_error_fallback() -> None:
    snapshot = _snapshot()
    provider = FakeClassificationProvider(
        {},
        failing_input_snapshot_ids=frozenset({snapshot.input_snapshot_id}),
    )

    result = ClassificationService(provider).classify(snapshot)

    _assert_fallback(result, snapshot, ClassificationFallbackReason.PROVIDER_ERROR)
    assert result.provider_model == provider.model_name


def test_service_revalidates_provider_clause_refs() -> None:
    snapshot = _snapshot()
    result_with_unknown_ref = _provider_result(
        snapshot,
        candidates=[
            ClauseCandidate(
                clause_ref="main_clauses:999",
                clause_type="other",
                clarity_candidate="확인 필요",
                responsible_party_candidate="미지정",
                condition_candidates=[],
                review_required=True,
            )
        ],
    )

    result = ClassificationService(
        NonValidatingProvider(result_with_unknown_ref)
    ).classify(snapshot)

    _assert_fallback(
        result,
        snapshot,
        ClassificationFallbackReason.RESPONSE_VALIDATION_FAILED,
    )


def test_input_validation_failure_skips_provider(monkeypatch) -> None:
    snapshot = _snapshot()
    provider = FakeClassificationProvider(
        {snapshot.input_snapshot_id: _provider_result(snapshot)}
    )

    def fail_builder(_: InputSnapshot) -> ClassificationInput:
        raise ValueError("원문 조항이 포함된 입력 오류")

    monkeypatch.setattr(
        "lease_companion_ai.classification.service.build_classification_input",
        fail_builder,
    )

    result = ClassificationService(provider).classify(snapshot)

    _assert_fallback(
        result,
        snapshot,
        ClassificationFallbackReason.INPUT_VALIDATION_FAILED,
    )
    assert provider.calls == []


def test_raw_provider_error_is_not_exposed_and_fallback_is_deterministic() -> None:
    snapshot = _snapshot()
    sensitive_error = "SDK raw response와 계좌번호 123-456-789"
    service = ClassificationService(RawFailingProvider(sensitive_error))

    first = service.classify(snapshot)
    second = service.classify(snapshot)

    assert first == second
    _assert_fallback(first, snapshot, ClassificationFallbackReason.PROVIDER_ERROR)
    assert sensitive_error not in first.model_dump_json()
