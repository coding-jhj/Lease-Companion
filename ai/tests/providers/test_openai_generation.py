from __future__ import annotations

import json
import sys
from types import MappingProxyType, SimpleNamespace

import pytest

from lease_companion_ai.generation.models import GeneratedGuidanceDraft
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.generation import (
    GenerationEvidence,
    GenerationRequest,
)
from lease_companion_ai.providers.openai_generation import OpenAIGenerationProvider


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


class FakeResponses:
    def __init__(self, output_parsed: object) -> None:
        self.output_parsed = output_parsed
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.output_parsed)


def test_openai_provider_uses_fixed_model_structured_output_and_limits():
    draft = GeneratedGuidanceDraft(
        explanation="등기 소유자를 직접 확인하십시오.",
        questions=("계약 상대가 등기 소유자와 같은가요?",),
        source_ids=("SRC-HTA-LAW",),
    )
    responses = FakeResponses(draft)
    provider = OpenAIGenerationProvider(
        client=SimpleNamespace(responses=responses),
        max_output_tokens=900,
    )

    assert provider.generate(_request()) == draft

    call = responses.calls[0]
    assert call["model"] == "gpt-5.6-sol"
    assert call["text_format"] is GeneratedGuidanceDraft
    assert call["max_output_tokens"] == 900
    assert call["reasoning"] == {"effort": "low"}
    assert call["store"] is False
    payload = json.loads(str(call["input"]))
    assert payload["rule"]["rule_id"] == "R01"
    assert payload["prompt_version"] == "v1"
    assert payload["official_evidence"][0]["source_id"] == "SRC-HTA-LAW"


def test_openai_provider_enforces_call_budget():
    responses = FakeResponses(
        GeneratedGuidanceDraft(
            explanation="직접 확인하십시오.", source_ids=("SRC-HTA-LAW",)
        )
    )
    provider = OpenAIGenerationProvider(
        client=SimpleNamespace(responses=responses), max_calls=1
    )

    provider.generate(_request())
    with pytest.raises(ProviderError, match="호출 예산"):
        provider.generate(_request())
    assert len(responses.calls) == 1


def test_openai_provider_rejects_request_without_official_evidence():
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
    provider = OpenAIGenerationProvider(client=SimpleNamespace())

    with pytest.raises(ProviderError, match="공식 근거"):
        provider.generate(request)


def test_openai_provider_does_not_require_sdk_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ProviderError, match="설정"):
        OpenAIGenerationProvider().generate(_request())


def test_openai_provider_configures_timeout_and_retries(monkeypatch):
    created: list[dict[str, object]] = []
    responses = FakeResponses(
        GeneratedGuidanceDraft(
            explanation="직접 확인하십시오.", source_ids=("SRC-HTA-LAW",)
        )
    )

    def build_client(**kwargs: object) -> object:
        created.append(kwargs)
        return SimpleNamespace(responses=responses)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=build_client))
    provider = OpenAIGenerationProvider(timeout_seconds=12.5, max_retries=1)

    provider.generate(_request())

    assert created == [
        {"api_key": "test-key", "timeout": 12.5, "max_retries": 1}
    ]


def test_openai_provider_sanitizes_sdk_errors():
    class FailingResponses:
        @staticmethod
        def parse(**kwargs: object) -> object:
            raise RuntimeError(f"secret input: {kwargs['input']}")

    provider = OpenAIGenerationProvider(
        client=SimpleNamespace(responses=FailingResponses())
    )

    with pytest.raises(ProviderError) as exc_info:
        provider.generate(_request())
    assert str(exc_info.value) == "OpenAI generation 호출에 실패했습니다."
    assert "등기 소유자" not in str(exc_info.value)
