from __future__ import annotations

import json
from types import MappingProxyType, SimpleNamespace

import pytest

from lease_companion_ai.generation.models import GeneratedGuidanceDraft
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
    def __init__(self, parsed: object, *, failures: int = 0) -> None:
        self.parsed = parsed
        self.failures = failures
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if len(self.calls) <= self.failures:
            raise RuntimeError(f"secret input: {kwargs['contents']}")
        return SimpleNamespace(parsed=self.parsed, text=None)


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
    models = FakeModels(draft, failures=2)
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
    assert str(exc_info.value) == "Gemini generation 호출에 실패했습니다."
    assert "등기 소유자" not in str(exc_info.value)
