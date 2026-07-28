from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.gemini_gateway import (
    GeminiCallPolicy,
    GeminiGateway,
    gemini_http_options,
)


@dataclass
class FakeApiError(RuntimeError):
    code: int
    message: str
    retry_after: float | None = None


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_gateway_retries_minute_quota_after_retry_after() -> None:
    clock = FakeClock()
    attempts = 0

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise FakeApiError(429, "rate limit per minute", retry_after=1.5)
        return "ok"

    gateway = GeminiGateway(
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        jitter=lambda: 0.0,
    )

    result = gateway.call(
        task="practice",
        model="test-model",
        operation=operation,
        policy=GeminiCallPolicy(max_attempts=2, max_total_wait_seconds=3),
    )

    assert result == "ok"
    assert attempts == 2
    assert clock.sleeps == [1.5]


def test_gateway_does_not_retry_daily_quota() -> None:
    clock = FakeClock()
    attempts = 0

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise FakeApiError(429, "requests per day quota exhausted")

    gateway = GeminiGateway(
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        jitter=lambda: 0.0,
    )

    with pytest.raises(ProviderError, match="할당량"):
        gateway.call(
            task="analysis",
            model="test-model",
            operation=operation,
            policy=GeminiCallPolicy(max_attempts=3, max_total_wait_seconds=15),
        )

    assert attempts == 1
    assert clock.sleeps == []


def test_gateway_does_not_retry_real_free_tier_daily_quota_id() -> None:
    """실제 응답의 quotaId는 공백이 없다(2026-07-23 실측). 재시도하면 안 된다."""
    clock = FakeClock()
    attempts = 0

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise FakeApiError(
            429,
            "RESOURCE_EXHAUSTED 'quotaId': "
            "'GenerateRequestsPerDayPerProjectPerModel-FreeTier', "
            "'retryDelay': '12s'",
            retry_after=12,
        )

    gateway = GeminiGateway(
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        jitter=lambda: 0.0,
    )

    with pytest.raises(ProviderError, match="일일 할당량"):
        gateway.call(
            task="document_extraction",
            model="test-model",
            operation=operation,
            policy=GeminiCallPolicy(max_attempts=3, max_total_wait_seconds=15),
        )

    assert attempts == 1
    assert clock.sleeps == []


def test_gateway_stops_when_retry_delay_exceeds_wait_budget() -> None:
    clock = FakeClock()
    attempts = 0

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise FakeApiError(503, "service unavailable", retry_after=20)

    gateway = GeminiGateway(
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        jitter=lambda: 0.0,
    )

    with pytest.raises(ProviderError, match="일시적으로"):
        gateway.call(
            task="generation",
            model="test-model",
            operation=operation,
            policy=GeminiCallPolicy(max_attempts=3, max_total_wait_seconds=15),
        )

    assert attempts == 1
    assert clock.sleeps == []


def test_gateway_enforces_configured_model_interval(monkeypatch) -> None:
    clock = FakeClock()
    monkeypatch.setenv("GEMINI_REQUESTS_PER_MINUTE", "60")
    gateway = GeminiGateway(
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        jitter=lambda: 0.0,
    )

    assert gateway.call(
        task="one",
        model="test-model",
        operation=lambda: "first",
        policy=GeminiCallPolicy(max_attempts=1, max_total_wait_seconds=0),
    ) == "first"
    assert gateway.call(
        task="two",
        model="test-model",
        operation=lambda: "second",
        policy=GeminiCallPolicy(max_attempts=1, max_total_wait_seconds=2),
    ) == "second"

    assert clock.sleeps == [1.0]


def test_http_options_disable_sdk_level_retries() -> None:
    options = gemini_http_options(30_000)

    assert options.timeout == 30_000
    assert options.retry_options.attempts == 1


def test_gateway_emits_usage_metric_without_prompt_content() -> None:
    clock = FakeClock()
    metrics = []
    gateway = GeminiGateway(
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        metric_sink=metrics.append,
        timestamp=lambda: "2026-07-28T12:00:00+00:00",
    )

    response = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=12,
            candidates_token_count=3,
            cached_content_token_count=2,
            total_token_count=15,
        )
    )
    result = gateway.call(
        task="generation",
        model="test-model",
        operation=lambda: response,
        policy=GeminiCallPolicy(max_attempts=1, max_total_wait_seconds=0),
    )

    assert result is response
    assert len(metrics) == 1
    assert metrics[0].provider == "gemini"
    assert metrics[0].input_tokens == 12
    assert metrics[0].output_tokens == 3
    assert metrics[0].ttfb_ms is None


def test_gateway_stream_measures_first_chunk_ttfb_and_total_latency() -> None:
    clock = FakeClock()
    metrics = []
    gateway = GeminiGateway(
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        metric_sink=metrics.append,
        timestamp=lambda: "2026-07-28T12:00:00+00:00",
    )

    def operation():
        clock.now += 0.125
        yield SimpleNamespace(text="첫", usage_metadata=None)
        clock.now += 0.375
        yield SimpleNamespace(
            text=" 응답",
            usage_metadata=SimpleNamespace(
                prompt_token_count=10,
                candidates_token_count=2,
                cached_content_token_count=0,
                total_token_count=12,
            ),
        )

    chunks = gateway.call_stream(
        task="ttfb_measurement",
        model="test-model",
        operation=operation,
        policy=GeminiCallPolicy(max_attempts=1, max_total_wait_seconds=0),
    )

    assert [chunk.text for chunk in chunks] == ["첫", " 응답"]
    assert metrics[0].ttfb_ms == 125
    assert metrics[0].latency_ms == 500
    assert metrics[0].input_tokens == 10
    assert metrics[0].output_tokens == 2
