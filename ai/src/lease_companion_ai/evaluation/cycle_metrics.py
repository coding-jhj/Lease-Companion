"""모드별 전체 사이클 provider 호출을 원문 없이 집계한다."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal, Sequence

from lease_companion_ai.evaluation.provider_metrics import ProviderCallMetric


CycleMode = Literal["actual_contract", "simulation"]


def _task_summary(rows: Sequence[ProviderCallMetric]) -> dict[str, Any]:
    known_costs = [
        row.estimated_cost for row in rows if row.estimated_cost is not None
    ]
    return {
        "call_count": len(rows),
        "success_count": sum(row.status == "success" for row in rows),
        "failure_count": sum(row.status != "success" for row in rows),
        "input_tokens": sum(row.input_tokens for row in rows),
        "output_tokens": sum(row.output_tokens for row in rows),
        "cached_tokens": sum(row.cached_tokens for row in rows),
        "search_units": sum(row.search_units for row in rows),
        "latency_ms": sum(row.latency_ms for row in rows),
        "known_cost_usd": (
            round(sum(known_costs), 12) if known_costs else None
        ),
        "unknown_cost_call_count": sum(
            row.estimated_cost is None for row in rows
        ),
    }


def build_cycle_summary(
    *,
    mode: CycleMode,
    calls: Sequence[ProviderCallMetric],
    cycle_count: int,
) -> dict[str, Any]:
    if cycle_count < 0:
        raise ValueError("cycle_count는 0 이상이어야 합니다.")
    grouped: dict[str, list[ProviderCallMetric]] = defaultdict(list)
    for call in calls:
        grouped[call.task].append(call)
    known_costs = [
        call.estimated_cost
        for call in calls
        if call.estimated_cost is not None
    ]
    known_cost = round(sum(known_costs), 12) if known_costs else 0.0
    return {
        "mode": mode,
        "cycle_count": cycle_count,
        "call_count": len(calls),
        "success_count": sum(call.status == "success" for call in calls),
        "failure_count": sum(call.status != "success" for call in calls),
        "input_tokens": sum(call.input_tokens for call in calls),
        "output_tokens": sum(call.output_tokens for call in calls),
        "cached_tokens": sum(call.cached_tokens for call in calls),
        "search_units": sum(call.search_units for call in calls),
        "total_latency_ms": sum(call.latency_ms for call in calls),
        "known_cost_usd": known_cost,
        "average_known_cost_usd_per_cycle": (
            round(known_cost / cycle_count, 12) if cycle_count else None
        ),
        "unknown_cost_call_count": sum(
            call.estimated_cost is None for call in calls
        ),
        "tasks": {
            task: _task_summary(rows)
            for task, rows in sorted(grouped.items())
        },
    }
