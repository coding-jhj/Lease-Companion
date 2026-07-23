from __future__ import annotations

from dataclasses import dataclass

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
