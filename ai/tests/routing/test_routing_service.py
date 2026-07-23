from __future__ import annotations

import pytest

from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderQuotaError,
    ProviderResponseValidationError,
)
from lease_companion_ai.routing.models import (
    ProcessingStage,
    RouteTarget,
    RoutingFailureReason,
)
from lease_companion_ai.routing.service import RoutingService


def _raise(error: ProviderError):
    def failing():
        raise error

    return failing


def test_unavailable_provider_skips_primary_and_selects_fallback():
    primary_called = False

    def primary():
        nonlocal primary_called
        primary_called = True
        return "provider"

    routed = RoutingService().execute(
        stage=ProcessingStage.EXTRACTION,
        primary_target=RouteTarget.GEMINI_EXTRACTION,
        fallback_target=RouteTarget.LOCAL_EXTRACTION,
        primary=primary,
        fallback=lambda: "local",
        primary_available=False,
    )

    assert routed.value == "local"
    assert primary_called is False
    assert routed.decision.primary_available is False
    assert routed.decision.failure_reason is RoutingFailureReason.PROVIDER_UNAVAILABLE


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (ProviderError("provider 호출 실패"), RoutingFailureReason.PROVIDER_ERROR),
        (
            ProviderError("구조화 추출용 GEMINI_API_KEY가 설정되지 않았습니다."),
            RoutingFailureReason.PROVIDER_UNAVAILABLE,
        ),
        (ProviderQuotaError("할당량 초과"), RoutingFailureReason.QUOTA_EXCEEDED),
        (
            ProviderResponseValidationError("응답 스키마 불일치"),
            RoutingFailureReason.RESPONSE_VALIDATION_FAILED,
        ),
    ],
)
def test_provider_failure_reason_is_recorded(error, expected_reason):
    routed = RoutingService().execute(
        stage=ProcessingStage.EXTRACTION,
        primary_target=RouteTarget.GEMINI_EXTRACTION,
        fallback_target=RouteTarget.LOCAL_EXTRACTION,
        primary=_raise(error),
        fallback=lambda: "local",
    )

    assert routed.value == "local"
    assert routed.decision.fallback_used is True
    assert routed.decision.failure_reason is expected_reason
    assert routed.decision.primary_available is (
        expected_reason is not RoutingFailureReason.PROVIDER_UNAVAILABLE
    )


def test_routing_log_contains_structured_reason_without_provider_message(caplog):
    caplog.set_level("INFO", logger="lease_companion_ai.routing.service")

    RoutingService().execute(
        stage=ProcessingStage.RERANK,
        primary_target=RouteTarget.COHERE_RERANK,
        fallback_target=RouteTarget.HYBRID_RANK,
        primary=_raise(ProviderQuotaError("민감한 provider 원문 할당량 오류")),
        fallback=lambda: "hybrid",
    )

    # 값이 extra에만 있으면 기본 포매터가 안 찍어 로그가 무의미해진다. 본문에 있어야 한다.
    record = next(
        record for record in caplog.records if "라우팅 fallback" in record.getMessage()
    )
    assert "reason=quota_exceeded" in record.getMessage()
    assert record.levelname == "WARNING"
    assert "민감한 provider 원문" not in record.getMessage()


def test_primary_failure_is_recorded_even_when_fallback_also_fails(caplog):
    caplog.set_level("INFO", logger="lease_companion_ai.routing.service")

    def failing_fallback():
        raise RuntimeError("local fallback 실패")

    with pytest.raises(RuntimeError, match="local fallback 실패"):
        RoutingService().execute(
            stage=ProcessingStage.EXTRACTION,
            primary_target=RouteTarget.GEMINI_EXTRACTION,
            fallback_target=RouteTarget.LOCAL_EXTRACTION,
            primary=_raise(ProviderQuotaError("할당량 초과")),
            fallback=failing_fallback,
        )

    record = next(
        record for record in caplog.records if "라우팅 fallback" in record.getMessage()
    )
    assert "reason=quota_exceeded" in record.getMessage()


@pytest.mark.parametrize(
    ("stage", "primary", "fallback"),
    [
        (
            ProcessingStage.EXTRACTION,
            RouteTarget.GEMINI_EXTRACTION,
            RouteTarget.LOCAL_EXTRACTION,
        ),
        (
            ProcessingStage.EMBEDDING,
            RouteTarget.GEMINI_EMBEDDING,
            RouteTarget.BM25,
        ),
        (
            ProcessingStage.RERANK,
            RouteTarget.COHERE_RERANK,
            RouteTarget.HYBRID_RANK,
        ),
    ],
)
def test_stage_specific_fallback_target_is_selected(stage, primary, fallback):
    routed = RoutingService().execute(
        stage=stage,
        primary_target=primary,
        fallback_target=fallback,
        primary=_raise(ProviderError("provider 오류")),
        fallback=lambda: fallback.value,
    )

    assert routed.value == fallback.value
    assert routed.decision.selected is fallback
    assert routed.decision.primary is primary
