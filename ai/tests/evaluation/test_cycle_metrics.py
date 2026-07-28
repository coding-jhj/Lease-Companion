from __future__ import annotations

from lease_companion_ai.evaluation.cycle_metrics import build_cycle_summary
from lease_companion_ai.evaluation.provider_metrics import ProviderCallMetric


def _call(
    *,
    provider: str,
    model: str,
    task: str,
    latency_ms: int,
    cost: float | None,
    status: str = "success",
) -> ProviderCallMetric:
    return ProviderCallMetric(
        timestamp="2026-07-28T00:00:00+00:00",
        provider=provider,
        model=model,
        task=task,
        status=status,
        attempt=1,
        latency_ms=latency_ms,
        ttfb_ms=None,
        input_tokens=10,
        output_tokens=5,
        cached_tokens=0,
        search_units=1 if provider == "cohere" else 0,
        estimated_cost=cost,
        currency="USD" if cost is not None else None,
        pricing_version="2026-07-21" if cost is not None else None,
    )


def test_cycle_summary_keeps_mode_tasks_cost_and_unknown_cost_separate() -> None:
    summary = build_cycle_summary(
        mode="actual_contract",
        calls=[
            _call(
                provider="gemini",
                model="gemini-3.5-flash",
                task="extraction",
                latency_ms=100,
                cost=0.01,
            ),
            _call(
                provider="cohere",
                model="rerank-v4.0-pro",
                task="rerank",
                latency_ms=50,
                cost=0.0,
            ),
            _call(
                provider="gemini",
                model="gemini-embedding-001",
                task="embedding",
                latency_ms=25,
                cost=None,
            ),
        ],
        cycle_count=1,
    )

    assert summary["mode"] == "actual_contract"
    assert summary["call_count"] == 3
    assert summary["success_count"] == 3
    assert summary["known_cost_usd"] == 0.01
    assert summary["average_known_cost_usd_per_cycle"] == 0.01
    assert summary["unknown_cost_call_count"] == 1
    assert summary["tasks"]["rerank"]["call_count"] == 1
    assert summary["tasks"]["embedding"]["input_tokens"] == 10


def test_cycle_summary_reports_failed_calls_without_counting_failed_cycle() -> None:
    summary = build_cycle_summary(
        mode="simulation",
        calls=[
            _call(
                provider="gemini",
                model="gemini-3.5-flash",
                task="practice_classification",
                latency_ms=100,
                cost=0.002,
                status="failure",
            )
        ],
        cycle_count=0,
    )

    assert summary["failure_count"] == 1
    assert summary["average_known_cost_usd_per_cycle"] is None
