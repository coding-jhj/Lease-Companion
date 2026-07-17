"""사용자 안내 생성 provider protocol과 결정적 fake provider."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

from lease_companion_ai.generation.models import GeneratedGuidanceDraft
from lease_companion_ai.providers.errors import ProviderError


@dataclass(frozen=True, slots=True)
class GenerationEvidence:
    source_id: str
    title: str
    institution: str
    summary: str | None
    source_url: str | None


@dataclass(frozen=True, slots=True)
class GenerationRequest:
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
