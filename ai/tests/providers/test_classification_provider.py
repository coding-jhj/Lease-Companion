from __future__ import annotations

from types import SimpleNamespace

import pytest

from lease_companion_ai.providers.classification import (
    CLASSIFICATION_PROMPT_VERSION,
    ClassificationProvider,
    FakeClassificationProvider,
    load_classification_prompt,
)
from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderResponseValidationError,
)
from lease_companion_ai.providers.gemini_classification import (
    GeminiClassificationProvider,
)
from lease_companion_ai.schemas import (
    ClassificationInput,
    ClassificationMethod,
    ClassificationResult,
    ClauseCandidate,
    ClauseInput,
)


def _input(text: str = "계약 종료일에 보증금을 반환한다.") -> ClassificationInput:
    return ClassificationInput(
        input_snapshot_id="SNAP-1",
        contract_id=1,
        clauses=[
            ClauseInput(
                clause_ref="deposit_return_clause:0",
                source_field="deposit_return_clause",
                ordinal=0,
                text=text,
            )
        ],
    )


def _candidate(clause_ref: str = "deposit_return_clause:0") -> ClauseCandidate:
    return ClauseCandidate(
        clause_ref=clause_ref,
        clause_type="deposit_return",
        clarity_candidate="명확",
        responsible_party_candidate="임대인",
        condition_candidates=["계약 종료일"],
        review_required=False,
    )


def _result(*, candidates: list[ClauseCandidate] | None = None) -> ClassificationResult:
    return ClassificationResult(
        input_snapshot_id="SNAP-1",
        contract_id=1,
        provider_model="fake-classification-v1",
        prompt_version=CLASSIFICATION_PROMPT_VERSION,
        classification_method=ClassificationMethod.PROVIDER,
        candidates=candidates if candidates is not None else [_candidate()],
    )


class FakeGeminiModels:
    def __init__(self, parsed: object) -> None:
        self.parsed = parsed
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(parsed=self.parsed)


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def call(self, **kwargs: object):
        self.calls.append(kwargs)
        return kwargs["operation"]()


class FailingGeminiModels:
    def __init__(self, sdk_error: str) -> None:
        self.sdk_error = sdk_error

    def generate_content(self, **_: object) -> object:
        raise RuntimeError(self.sdk_error)


def test_fake_classification_provider_satisfies_protocol_and_records_calls() -> None:
    provider = FakeClassificationProvider({"SNAP-1": _result()})

    result = provider.classify(_input())

    assert isinstance(provider, ClassificationProvider)
    assert result.candidates == [_candidate()]
    assert provider.calls == [_input()]


@pytest.mark.parametrize(
    "invalid_candidates",
    [
        [_candidate("main_clauses:0")],
        [_candidate(), _candidate()],
    ],
)
def test_fake_classification_provider_rejects_invalid_clause_refs(
    invalid_candidates: list[ClauseCandidate],
) -> None:
    invalid = ClassificationResult.model_construct(
        input_snapshot_id="SNAP-1",
        contract_id=1,
        provider_model="fake-classification-v1",
        prompt_version=CLASSIFICATION_PROMPT_VERSION,
        classification_method=ClassificationMethod.PROVIDER,
        fallback_reason_code=None,
        candidates=invalid_candidates,
    )
    provider = FakeClassificationProvider({"SNAP-1": invalid})

    with pytest.raises(ProviderResponseValidationError, match="응답 검증"):
        provider.classify(_input())


def test_classification_prompt_file_matches_version_constant() -> None:
    prompt = load_classification_prompt()

    assert CLASSIFICATION_PROMPT_VERSION == "classification-v1"
    assert prompt.splitlines()[0] == "버전: classification-v1"


def test_gemini_classification_provider_wraps_canonical_result() -> None:
    models = FakeGeminiModels(
        {
            "candidates": [
                {
                    "clause_ref": "deposit_return_clause:0",
                    "clause_type": "deposit_return",
                    "clarity_candidate": "명확",
                    "responsible_party_candidate": "임대인",
                    "condition_candidates": ["계약 종료일"],
                    "review_required": False,
                }
            ]
        }
    )
    provider = GeminiClassificationProvider(client=SimpleNamespace(models=models))

    result = provider.classify(_input())

    assert result == ClassificationResult(
        input_snapshot_id="SNAP-1",
        contract_id=1,
        provider_model="gemini/gemini-3.5-flash",
        prompt_version=CLASSIFICATION_PROMPT_VERSION,
        classification_method="provider",
        candidates=[_candidate()],
    )
    assert models.calls[0]["model"] == "gemini-3.5-flash"


def test_gemini_classification_routes_transport_through_gateway() -> None:
    models = FakeGeminiModels({"candidates": []})
    gateway = RecordingGateway()
    provider = GeminiClassificationProvider(
        client=SimpleNamespace(models=models), gateway=gateway
    )

    provider.classify(_input())

    assert len(gateway.calls) == 1
    assert gateway.calls[0]["task"] == "clause_classification"


def test_gemini_provider_rejects_rule_fields_in_response() -> None:
    models = FakeGeminiModels(
        {
            "candidates": [
                {
                    "clause_ref": "deposit_return_clause:0",
                    "clause_type": "deposit_return",
                    "clarity_candidate": "명확",
                    "responsible_party_candidate": "임대인",
                    "condition_candidates": [],
                    "review_required": False,
                    "status": "확인 필요",
                }
            ]
        }
    )
    provider = GeminiClassificationProvider(client=SimpleNamespace(models=models))

    with pytest.raises(ProviderResponseValidationError, match="응답 검증"):
        provider.classify(_input())


def test_gemini_provider_does_not_require_key_until_real_call(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(ProviderError, match="설정"):
        GeminiClassificationProvider().classify(_input())


def test_gemini_provider_does_not_expose_clause_or_sdk_error() -> None:
    sensitive_text = "계좌번호 123-456-789가 포함된 조항"
    sdk_error = f"SDK raw response: {sensitive_text}"
    provider = GeminiClassificationProvider(
        client=SimpleNamespace(models=FailingGeminiModels(sdk_error))
    )

    with pytest.raises(ProviderError) as error:
        provider.classify(_input(sensitive_text))

    assert str(error.value) == "Gemini 호출에 실패했습니다."
    assert sensitive_text not in str(error.value)
    assert sdk_error not in str(error.value)
