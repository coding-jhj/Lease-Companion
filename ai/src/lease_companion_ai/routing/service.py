"""provider 실행과 결정론적 fallback 선택을 한 곳에서 기록한다."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Generic, TypeVar

from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderQuotaError,
    ProviderResponseValidationError,
    ProviderUnavailableError,
)
from lease_companion_ai.routing.models import (
    ProcessingStage,
    RouteTarget,
    RoutingDecision,
    RoutingFailureReason,
)


T = TypeVar("T")
logger = logging.getLogger(__name__)


def _record_decision(decision: RoutingDecision) -> None:
    logger.info(
        "ai_routing_decision",
        extra={"routing_decision": decision.to_dict()},
    )


@dataclass(frozen=True, slots=True)
class RoutedExecution(Generic[T]):
    value: T
    decision: RoutingDecision


def classify_provider_failure(error: BaseException) -> RoutingFailureReason:
    if isinstance(error, ProviderUnavailableError):
        return RoutingFailureReason.PROVIDER_UNAVAILABLE
    if isinstance(error, ProviderQuotaError):
        return RoutingFailureReason.QUOTA_EXCEEDED
    if isinstance(error, ProviderResponseValidationError):
        return RoutingFailureReason.RESPONSE_VALIDATION_FAILED

    message = str(error).lower()
    if any(marker in message for marker in ("할당량", "한도", "quota", "budget")):
        return RoutingFailureReason.QUOTA_EXCEEDED
    if any(
        marker in message
        for marker in (
            "설정이 없습니다",
            "설정되지 않았습니다",
            "api_key",
            "sdk",
            "google-genai가 필요",
        )
    ):
        return RoutingFailureReason.PROVIDER_UNAVAILABLE
    if any(
        marker in message
        for marker in (
            "응답",
            "스키마",
            "구조화하지 못",
            "결과가 비어",
            "차원",
            "인덱스",
            "점수",
        )
    ):
        return RoutingFailureReason.RESPONSE_VALIDATION_FAILED
    return RoutingFailureReason.PROVIDER_ERROR


class RoutingService:
    """primary를 한 번 실행하고 실패하면 명시된 fallback을 선택한다."""

    def execute(
        self,
        *,
        stage: ProcessingStage,
        primary_target: RouteTarget,
        fallback_target: RouteTarget,
        primary: Callable[[], T],
        fallback: Callable[[], T],
        primary_available: bool = True,
        handled_errors: tuple[type[BaseException], ...] = (ProviderError,),
    ) -> RoutedExecution[T]:
        if not primary_available:
            decision = self.fallback_decision(
                stage=stage,
                primary_target=primary_target,
                fallback_target=fallback_target,
                reason=RoutingFailureReason.PROVIDER_UNAVAILABLE,
                primary_available=False,
            )
            return RoutedExecution(
                value=fallback(),
                decision=decision,
            )
        try:
            value = primary()
        except handled_errors as error:
            reason = classify_provider_failure(error)
            decision = self.fallback_decision(
                stage=stage,
                primary_target=primary_target,
                fallback_target=fallback_target,
                reason=reason,
                primary_available=(
                    reason is not RoutingFailureReason.PROVIDER_UNAVAILABLE
                ),
            )
            return RoutedExecution(
                value=fallback(),
                decision=decision,
            )
        decision = RoutingDecision(
            stage=stage,
            primary=primary_target,
            selected=primary_target,
            primary_available=True,
            fallback_used=False,
        )
        _record_decision(decision)
        return RoutedExecution(
            value=value,
            decision=decision,
        )

    @staticmethod
    def fallback_decision(
        *,
        stage: ProcessingStage,
        primary_target: RouteTarget,
        fallback_target: RouteTarget,
        reason: RoutingFailureReason,
        primary_available: bool,
    ) -> RoutingDecision:
        decision = RoutingDecision(
            stage=stage,
            primary=primary_target,
            selected=fallback_target,
            primary_available=primary_available,
            fallback_used=True,
            failure_reason=reason,
        )
        _record_decision(decision)
        return decision
