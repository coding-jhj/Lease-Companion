"""Classification provider protocol과 결정적 fake provider."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping, Protocol, runtime_checkable

from pydantic import ValidationError

from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderResponseValidationError,
)
from lease_companion_ai.schemas import (
    ClassificationInput,
    ClassificationResult,
    validate_classification_result_for_input,
)

CLASSIFICATION_PROMPT_VERSION: Final = "classification-v1"


def load_classification_prompt(root: Path | None = None) -> str:
    """버전 헤더가 일치하는 classification prompt를 읽는다."""

    prompt_root = root or Path(__file__).resolve().parents[3] / "prompts"
    prompt = (prompt_root / "classification" / "v1.txt").read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("classification 프롬프트는 비어 있을 수 없습니다.")
    expected_header = f"버전: {CLASSIFICATION_PROMPT_VERSION}"
    if prompt.splitlines()[0].strip() != expected_header:
        raise ValueError(f"classification 프롬프트 헤더는 {expected_header}이어야 합니다.")
    return prompt


def validate_provider_result(
    classification_input: ClassificationInput,
    result: ClassificationResult,
) -> ClassificationResult:
    """Provider 결과를 canonical 모델로 재검증하고 입력과 교차 검증한다."""

    try:
        validated = ClassificationResult.model_validate(result.model_dump(mode="python"))
        return validate_classification_result_for_input(classification_input, validated)
    except (TypeError, ValueError, ValidationError):
        raise ProviderResponseValidationError(
            "classification provider 응답 검증에 실패했습니다."
        ) from None


@runtime_checkable
class ClassificationProvider(Protocol):
    model_name: str

    def classify(
        self, classification_input: ClassificationInput
    ) -> ClassificationResult: ...


class FakeClassificationProvider:
    """외부 호출 없이 classification 계약을 검증하는 결정적 provider."""

    model_name = "fake-classification-v1"

    def __init__(
        self,
        outputs: Mapping[str, ClassificationResult],
        *,
        failing_input_snapshot_ids: frozenset[str] = frozenset(),
    ) -> None:
        self._outputs = MappingProxyType(dict(outputs))
        self._failing_input_snapshot_ids = failing_input_snapshot_ids
        self.calls: list[ClassificationInput] = []

    def classify(
        self, classification_input: ClassificationInput
    ) -> ClassificationResult:
        self.calls.append(classification_input)
        snapshot_id = classification_input.input_snapshot_id
        if snapshot_id in self._failing_input_snapshot_ids:
            raise ProviderError("fake classification provider failure")
        try:
            result = self._outputs[snapshot_id]
        except KeyError:
            raise ProviderError("fake classification output is missing") from None
        return validate_provider_result(classification_input, result)
