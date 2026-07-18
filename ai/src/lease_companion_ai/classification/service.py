"""Classification provider 실행과 안전한 fallback을 조정한다."""

from __future__ import annotations

from enum import Enum

from lease_companion_ai.classification.builder import build_classification_input
from lease_companion_ai.providers.classification import (
    CLASSIFICATION_PROMPT_VERSION,
    ClassificationProvider,
)
from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderResponseValidationError,
)
from lease_companion_ai.routing.models import RoutingFailureReason
from lease_companion_ai.routing.service import classify_provider_failure
from lease_companion_ai.schemas import (
    ClassificationMethod,
    ClassificationResult,
    validate_classification_result_for_input,
)
from lease_companion_ai.schemas.unified import InputSnapshot


class ClassificationFallbackReason(str, Enum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_ERROR = "provider_error"
    RESPONSE_VALIDATION_FAILED = "response_validation_failed"
    INPUT_VALIDATION_FAILED = "input_validation_failed"


class ClassificationService:
    """Snapshot을 분류하고 실패 시 후보 없는 canonical 결과를 반환한다."""

    def __init__(self, provider: ClassificationProvider | None = None) -> None:
        self._provider = provider

    def classify(self, snapshot: InputSnapshot) -> ClassificationResult:
        try:
            classification_input = build_classification_input(snapshot)
        except (TypeError, ValueError):
            return self._safe_fallback(
                snapshot,
                ClassificationFallbackReason.INPUT_VALIDATION_FAILED,
            )

        if self._provider is None:
            return self._safe_fallback(
                snapshot,
                ClassificationFallbackReason.PROVIDER_UNAVAILABLE,
            )

        try:
            result = self._provider.classify(classification_input)
        except ProviderResponseValidationError:
            return self._safe_fallback(
                snapshot,
                ClassificationFallbackReason.RESPONSE_VALIDATION_FAILED,
            )
        except ProviderError as error:
            return self._safe_fallback(
                snapshot,
                self._provider_failure_reason(error),
            )
        except Exception:
            return self._safe_fallback(
                snapshot,
                ClassificationFallbackReason.PROVIDER_ERROR,
            )

        try:
            return validate_classification_result_for_input(
                classification_input,
                result,
            )
        except (AttributeError, TypeError, ValueError):
            return self._safe_fallback(
                snapshot,
                ClassificationFallbackReason.RESPONSE_VALIDATION_FAILED,
            )

    def _safe_fallback(
        self,
        snapshot: InputSnapshot,
        reason: ClassificationFallbackReason,
    ) -> ClassificationResult:
        return ClassificationResult(
            schema_version=snapshot.schema_version,
            input_snapshot_id=snapshot.input_snapshot_id,
            contract_id=snapshot.contract_id,
            provider_model=self._provider_model(),
            prompt_version=CLASSIFICATION_PROMPT_VERSION,
            classification_method=ClassificationMethod.SAFE_FALLBACK,
            fallback_reason_code=reason.value,
            candidates=[],
        )

    def _provider_model(self) -> str:
        if self._provider is None:
            return "unconfigured"
        model_name = self._provider.model_name.strip()
        return model_name or "unconfigured"

    @staticmethod
    def _provider_failure_reason(
        error: ProviderError,
    ) -> ClassificationFallbackReason:
        routing_reason = classify_provider_failure(error)
        if routing_reason is RoutingFailureReason.PROVIDER_UNAVAILABLE:
            return ClassificationFallbackReason.PROVIDER_UNAVAILABLE
        if routing_reason is RoutingFailureReason.RESPONSE_VALIDATION_FAILED:
            return ClassificationFallbackReason.RESPONSE_VALIDATION_FAILED
        return ClassificationFallbackReason.PROVIDER_ERROR
