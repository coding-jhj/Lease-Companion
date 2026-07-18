"""사용자 안내 생성 provider protocol과 결정적 fake provider."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

from lease_companion_ai.generation.models import GeneratedGuidanceDraft
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.schemas.unified import GenerationPromptVersion


@dataclass(frozen=True, slots=True)
class GenerationEvidence:
    source_id: str
    title: str
    institution: str
    summary: str | None
    source_url: str | None


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """R 규칙 또는 J 판정 하나를 생성 provider에 전달하는 내부 요청."""

    prompt_version: GenerationPromptVersion
    # 기존 provider wire 호환을 위해 이름은 rule_id/rule_name을 유지하며 J ID도 허용한다.
    rule_id: str
    rule_name: str
    status: str
    urgency: str
    reason: str
    limitations: str
    evidence: tuple[GenerationEvidence, ...]
    prompts: Mapping[str, str]


@runtime_checkable
class GenerationProvider(Protocol):
    model_name: str

    def generate(self, request: GenerationRequest) -> GeneratedGuidanceDraft: ...


class FakeGenerationProvider:
    """외부 호출 없이 생성 서비스 계약을 검증하는 결정적 provider."""

    model_name = "fake-generation-v1"

    def __init__(
        self,
        outputs: Mapping[str, GeneratedGuidanceDraft],
        *,
        failing_rule_ids: frozenset[str] = frozenset(),
    ) -> None:
        self._outputs = MappingProxyType(dict(outputs))
        self._failing_rule_ids = failing_rule_ids
        self.calls: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GeneratedGuidanceDraft:
        self.calls.append(request)
        if request.rule_id in self._failing_rule_ids:
            raise ProviderError("fake generation provider failure")
        try:
            return self._outputs[request.rule_id]
        except KeyError as exc:
            raise ProviderError("fake generation output is missing") from exc
