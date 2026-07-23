"""Gemini 호출의 속도 제한·오류 분류·재시도를 한 경계에서 관리한다."""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderQuotaError,
    ProviderTemporaryError,
    ProviderTimeoutError,
)


logger = logging.getLogger(__name__)
T = TypeVar("T")
_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
_NON_RETRYABLE_STATUS_CODES = frozenset({400, 401, 403, 404})
_DAILY_QUOTA_MARKERS = (
    "per day",
    "requests per day",
    "daily",
    "quota per day",
)


@dataclass(frozen=True, slots=True)
class GeminiCallPolicy:
    max_attempts: int
    max_total_wait_seconds: float

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError("max_attempts는 양수여야 합니다.")
        if self.max_total_wait_seconds < 0:
            raise ValueError("max_total_wait_seconds는 0 이상이어야 합니다.")


def _status_code(exc: Exception) -> int | None:
    for name in ("code", "status_code"):
        value = getattr(exc, name, None)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    text = str(exc)
    for code in (*_RETRYABLE_STATUS_CODES, *_NON_RETRYABLE_STATUS_CODES):
        if str(code) in text:
            return code
    return None


def _retry_after(exc: Exception) -> float | None:
    value = getattr(exc, "retry_after", None)
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        raw = headers.get("Retry-After")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None
    return None


def _is_daily_quota(exc: Exception) -> bool:
    detail = " ".join(
        str(value)
        for value in (
            getattr(exc, "message", ""),
            getattr(exc, "quota_id", ""),
            getattr(exc, "quota_metric", ""),
            str(exc),
        )
    ).lower()
    return any(marker in detail for marker in _DAILY_QUOTA_MARKERS)


class GeminiGateway:
    """프로세스 안에서 Gemini 호출을 직렬화하고 제한적으로 재시도한다."""

    def __init__(
        self,
        *,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        jitter: Callable[[], float] = random.random,
        max_concurrency: int | None = None,
    ) -> None:
        configured_concurrency = max_concurrency or int(
            os.getenv("GEMINI_MAX_CONCURRENCY", "1")
        )
        if configured_concurrency <= 0:
            raise ValueError("GEMINI_MAX_CONCURRENCY는 양수여야 합니다.")
        self._semaphore = threading.BoundedSemaphore(configured_concurrency)
        self._rate_lock = threading.Lock()
        self._next_call_at: dict[str, float] = {}
        self._sleep = sleep
        self._monotonic = monotonic
        self._jitter = jitter

    @staticmethod
    def _minimum_interval() -> float:
        raw = os.getenv("GEMINI_REQUESTS_PER_MINUTE")
        if not raw:
            return 0.0
        try:
            rpm = float(raw)
        except ValueError as exc:
            raise ValueError("GEMINI_REQUESTS_PER_MINUTE는 숫자여야 합니다.") from exc
        if rpm <= 0:
            raise ValueError("GEMINI_REQUESTS_PER_MINUTE는 양수여야 합니다.")
        return 60.0 / rpm

    def _wait_for_rate_slot(self, model: str, remaining_wait: float) -> float:
        interval = self._minimum_interval()
        if interval <= 0:
            return 0.0
        with self._rate_lock:
            now = self._monotonic()
            delay = max(0.0, self._next_call_at.get(model, now) - now)
            if delay > remaining_wait:
                raise ProviderQuotaError("Gemini 호출 속도 제한 대기 예산을 초과했습니다.")
            if delay:
                self._sleep(delay)
                now = self._monotonic()
            self._next_call_at[model] = now + interval
            return delay

    def call(
        self,
        *,
        task: str,
        model: str,
        operation: Callable[[], T],
        policy: GeminiCallPolicy,
    ) -> T:
        waited = 0.0
        unknown_quota_retries = 0
        for attempt in range(1, policy.max_attempts + 1):
            waited += self._wait_for_rate_slot(
                model, policy.max_total_wait_seconds - waited
            )
            started = self._monotonic()
            try:
                with self._semaphore:
                    result = operation()
                logger.info(
                    "Gemini 호출 성공 task=%s model=%s attempt=%d latency_ms=%d",
                    task,
                    model,
                    attempt,
                    int((self._monotonic() - started) * 1000),
                )
                return result
            except ProviderError:
                raise
            except Exception as exc:
                timed_out = isinstance(exc, TimeoutError) or "timeout" in type(
                    exc
                ).__name__.lower()
                status = _status_code(exc)
                daily_quota = status == 429 and _is_daily_quota(exc)
                retryable = (
                    status in _RETRYABLE_STATUS_CODES
                    or timed_out
                    or isinstance(exc, ConnectionError)
                )
                if daily_quota:
                    raise ProviderQuotaError("Gemini 일일 할당량을 초과했습니다.") from None
                if status in _NON_RETRYABLE_STATUS_CODES or not retryable:
                    raise ProviderError("Gemini 호출에 실패했습니다.") from None
                if status == 429 and not _retry_after(exc):
                    unknown_quota_retries += 1
                    if unknown_quota_retries > 1:
                        raise ProviderQuotaError("Gemini 할당량을 초과했습니다.") from None
                if attempt == policy.max_attempts:
                    if timed_out:
                        raise ProviderTimeoutError("Gemini 호출 시간이 초과되었습니다.") from None
                    raise ProviderTemporaryError("Gemini 서비스를 일시적으로 사용할 수 없습니다.") from None
                delay = _retry_after(exc)
                if delay is None:
                    delay = min(30.0, float(2 ** (attempt - 1))) + self._jitter()
                if waited + delay > policy.max_total_wait_seconds:
                    if timed_out:
                        raise ProviderTimeoutError("Gemini 호출 시간이 초과되었습니다.") from None
                    raise ProviderTemporaryError("Gemini 서비스를 일시적으로 사용할 수 없습니다.") from None
                logger.warning(
                    "Gemini 호출 재시도 task=%s model=%s attempt=%d status=%s wait_ms=%d",
                    task,
                    model,
                    attempt,
                    status,
                    int(delay * 1000),
                )
                self._sleep(delay)
                waited += delay
        raise ProviderError("Gemini 호출에 실패했습니다.")


_gateway: GeminiGateway | None = None
_gateway_lock = threading.Lock()


def get_gemini_gateway() -> GeminiGateway:
    global _gateway
    with _gateway_lock:
        if _gateway is None:
            _gateway = GeminiGateway()
        return _gateway


def gemini_http_options(timeout_ms: int):
    """SDK 자체 재시도를 1회 시도로 고정해 Gateway와 중첩되지 않게 한다."""
    from google.genai import types

    return types.HttpOptions(
        timeout=timeout_ms,
        retry_options=types.HttpRetryOptions(attempts=1),
    )
