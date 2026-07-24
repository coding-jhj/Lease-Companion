from __future__ import annotations

import json
from dataclasses import replace
from types import MappingProxyType, SimpleNamespace

import pytest

from lease_companion_ai.generation.models import (
    GeneratedGuidanceBatch,
    GeneratedGuidanceBatchItem,
    GeneratedGuidanceDraft,
)
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.gemini_generation import GeminiGenerationProvider
from lease_companion_ai.providers.generation import (
    GenerationEvidence,
    GenerationRequest,
)


def _request() -> GenerationRequest:
    return GenerationRequest(
        prompt_version="v1",
        rule_id="R01",
        rule_name="임대인과 등기 소유자 일치",
        status="확인 필요",
        urgency="계약 전 확인",
        reason="등기 소유자를 확인해야 합니다.",
        limitations="제공된 문서 범위",
        evidence=(
            GenerationEvidence(
                source_id="SRC-HTA-LAW",
                title="주택임대차보호법",
                institution="국가법령정보센터",
                summary="임차인의 권리 보호 기준",
                source_url="https://law.go.kr/example",
            ),
        ),
        prompts=MappingProxyType(
            {
                "questions": "확인 질문을 작성하십시오.",
                "checklists": "체크리스트를 작성하십시오.",
                "summaries": "쉬운 설명을 작성하십시오.",
            }
        ),
    )


class FakeModels:
    def __init__(
        self,
        parsed: object,
        *,
        failures: int = 0,
        failure_type: type[Exception] = RuntimeError,
    ) -> None:
        self.parsed = parsed
        self.failures = failures
        self.failure_type = failure_type
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if len(self.calls) <= self.failures:
            raise self.failure_type(f"secret input: {kwargs['contents']}")
        return SimpleNamespace(parsed=self.parsed, text=None)


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def call(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return kwargs["operation"]()


def test_gemini_provider_uses_fixed_model_structured_output_and_limits():
    draft = GeneratedGuidanceDraft(
        explanation="등기 소유자를 직접 확인하십시오.",
        questions=("계약 상대가 등기 소유자와 같은가요?",),
        source_ids=("SRC-HTA-LAW",),
    )
    models = FakeModels(draft)
    provider = GeminiGenerationProvider(
        client=SimpleNamespace(models=models),
        max_output_tokens=900,
    )

    assert provider.generate(_request()) == draft

    call = models.calls[0]
    assert call["model"] == "gemini-3.5-flash"
    config = call["config"]
    # Gemini는 additionalProperties를 거부하므로 정리된 스키마(dict)를 넘긴다.
    assert isinstance(config.response_schema, dict)
    assert set(config.response_schema["properties"]) == {
            "explanation",
            "questions",
            "request_templates",
            "signing_checklist",
        "post_contract_actions",
        "source_ids",
    }
    assert "additionalProperties" not in json.dumps(config.response_schema)
    # thinking 모델의 추론 토큰이 답변 budget을 잠식하지 않도록 thinking을 끈다.
    assert config.thinking_config.thinking_budget == 0
    assert config.response_mime_type == "application/json"
    assert config.max_output_tokens == 900
    assert config.temperature == 0
    payload = json.loads(str(call["contents"][1]))
    assert payload["rule"]["rule_id"] == "R01"
    assert payload["prompt_version"] == "v1"
    assert payload["official_evidence"][0]["source_id"] == "SRC-HTA-LAW"


def test_gemini_generation_routes_transport_through_gateway():
    draft = GeneratedGuidanceDraft(
        explanation="직접 확인하십시오.", source_ids=("SRC-HTA-LAW",)
    )
    gateway = RecordingGateway()
    provider = GeminiGenerationProvider(
        client=SimpleNamespace(models=FakeModels(draft)), gateway=gateway
    )

    assert provider.generate(_request()) == draft
    assert len(gateway.calls) == 1
    assert gateway.calls[0]["task"] == "report_generation"
    assert gateway.calls[0]["model"] == "gemini-3.5-flash"


def test_gemini_generation_model_can_be_configured(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_GENERATION", "configured-model")

    provider = GeminiGenerationProvider(client=SimpleNamespace())

    assert provider.model_name == "configured-model"


def test_gemini_generation_batches_multiple_requests_into_one_sdk_call():
    batch = GeneratedGuidanceBatch(
        items=(
            GeneratedGuidanceBatchItem(
                item_id="R01",
                explanation="R01을 확인하세요.",
                source_ids=("SRC-HTA-LAW",),
            ),
            GeneratedGuidanceBatchItem(
                item_id="R02",
                explanation="R02를 확인하세요.",
                source_ids=("SRC-HTA-LAW",),
            ),
        )
    )
    models = FakeModels(batch)
    provider = GeminiGenerationProvider(client=SimpleNamespace(models=models))
    second = replace(_request(), rule_id="R02")

    result = provider.generate_batch((_request(), second))

    assert set(result) == {"R01", "R02"}
    assert result["R01"].explanation == "R01을 확인하세요."
    assert len(models.calls) == 1
    payload = json.loads(str(models.calls[0]["contents"][1]))
    assert [item["rule"]["rule_id"] for item in payload["items"]] == ["R01", "R02"]


def _batch_of(*rule_ids: str) -> GeneratedGuidanceBatch:
    return GeneratedGuidanceBatch(
        items=tuple(
            GeneratedGuidanceBatchItem(
                item_id=rule_id,
                explanation=f"{rule_id}을 확인하세요.",
                source_ids=("SRC-HTA-LAW",),
            )
            for rule_id in rule_ids
        )
    )


def _requests(count: int) -> tuple[GenerationRequest, ...]:
    return tuple(
        replace(_request(), rule_id=f"R{index:02d}")
        for index in range(1, count + 1)
    )


def test_gemini_generation_splits_batch_to_fit_output_budget():
    """한 번에 다 보내면 응답이 잘려 배치 전체가 무효가 된다(2026-07-23 실측)."""
    requests = _requests(6)
    models = FakeModels(_batch_of(*(request.rule_id for request in requests)))
    # 출력 예산 800 → 항목당 400 → 호출당 2건
    provider = GeminiGenerationProvider(
        client=SimpleNamespace(models=models), max_output_tokens=800
    )

    result = provider.generate_batch(requests)

    assert set(result) == {request.rule_id for request in requests}
    assert len(models.calls) == 3
    for call in models.calls:
        payload = json.loads(str(call["contents"][1]))
        assert len(payload["items"]) == 2
        # 출력 토큰은 청크 항목 수에 비례해야 한다.
        assert call["config"].max_output_tokens >= 800


def test_gemini_generation_keeps_successful_chunks_when_one_chunk_fails():
    requests = _requests(4)
    models = FakeModels(
        _batch_of(*(request.rule_id for request in requests)), failures=1
    )
    provider = GeminiGenerationProvider(
        client=SimpleNamespace(models=models), max_output_tokens=800, max_retries=0
    )

    result = provider.generate_batch(requests)

    # 첫 청크(R01·R02)는 실패, 둘째 청크(R03·R04)는 살아남는다.
    assert set(result) == {"R03", "R04"}


def test_gemini_generation_raises_when_every_chunk_fails():
    requests = _requests(4)
    models = FakeModels(_batch_of("R01"), failures=2)
    provider = GeminiGenerationProvider(
        client=SimpleNamespace(models=models), max_output_tokens=800, max_retries=0
    )

    with pytest.raises(ProviderError):
        provider.generate_batch(requests)


def test_gemini_provider_enforces_call_budget():
    models = FakeModels(
        GeneratedGuidanceDraft(
            explanation="직접 확인하십시오.", source_ids=("SRC-HTA-LAW",)
        )
    )
    provider = GeminiGenerationProvider(
        client=SimpleNamespace(models=models), max_calls=1
    )

    provider.generate(_request())
    with pytest.raises(ProviderError, match="호출 예산"):
        provider.generate(_request())
    assert len(models.calls) == 1


def test_gemini_provider_rejects_request_without_official_evidence():
    request = _request()
    request = GenerationRequest(
        prompt_version=request.prompt_version,
        rule_id=request.rule_id,
        rule_name=request.rule_name,
        status=request.status,
        urgency=request.urgency,
        reason=request.reason,
        limitations=request.limitations,
        evidence=(),
        prompts=request.prompts,
    )
    provider = GeminiGenerationProvider(client=SimpleNamespace())

    with pytest.raises(ProviderError, match="공식 근거"):
        provider.generate(request)


def test_gemini_provider_serializes_deidentified_special_clause_text():
    request = _request()
    request = GenerationRequest(
        prompt_version=request.prompt_version,
        rule_id="CLAUSE-001",
        rule_name="SC-DEFERRED-REFUND",
        status=request.status,
        urgency=request.urgency,
        reason=request.reason,
        limitations=request.limitations,
        evidence=request.evidence,
        prompts=request.prompts,
        deidentified_clause_text="[PERSON_1]과 반환 조건을 확인한다.",
    )

    payload = json.loads(GeminiGenerationProvider._serialize_request(request))

    assert payload["deidentified_clause_text"] == "[PERSON_1]과 반환 조건을 확인한다."


def test_gemini_provider_does_not_require_sdk_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(ProviderError, match="설정"):
        GeminiGenerationProvider().generate(_request())


def test_gemini_provider_retries_transient_errors():
    draft = GeneratedGuidanceDraft(
        explanation="직접 확인하십시오.", source_ids=("SRC-HTA-LAW",)
    )
    models = FakeModels(draft, failures=2, failure_type=TimeoutError)
    provider = GeminiGenerationProvider(
        client=SimpleNamespace(models=models), max_retries=2
    )

    assert provider.generate(_request()) == draft
    assert len(models.calls) == 3


def test_gemini_provider_sanitizes_sdk_errors():
    models = FakeModels(SimpleNamespace(), failures=3)
    provider = GeminiGenerationProvider(
        client=SimpleNamespace(models=models), max_retries=2
    )

    with pytest.raises(ProviderError) as exc_info:
        provider.generate(_request())
    assert str(exc_info.value) == "Gemini 호출에 실패했습니다."
    assert "등기 소유자" not in str(exc_info.value)
