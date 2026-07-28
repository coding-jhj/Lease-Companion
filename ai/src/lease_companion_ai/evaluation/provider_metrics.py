"""상용 provider 호출 메타데이터를 원문 없이 기록·집계한다."""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from dataclasses import replace
from pathlib import Path
from typing import Any


def _integer(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def extract_gemini_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage_metadata", None)
    return {
        "input_tokens": _integer(getattr(usage, "prompt_token_count", 0)),
        "output_tokens": _integer(getattr(usage, "candidates_token_count", 0)),
        "cached_tokens": _integer(
            getattr(usage, "cached_content_token_count", 0)
        ),
        "total_tokens": _integer(getattr(usage, "total_token_count", 0)),
    }


def extract_cohere_usage(response: Any) -> dict[str, int]:
    meta = getattr(response, "meta", None)
    billed_units = getattr(meta, "billed_units", None)
    tokens = getattr(meta, "tokens", None)
    return {
        "input_tokens": _integer(getattr(tokens, "input_tokens", 0)),
        "output_tokens": _integer(getattr(tokens, "output_tokens", 0)),
        "search_units": _integer(getattr(billed_units, "search_units", 0)),
    }


@dataclass(frozen=True, slots=True)
class ProviderCallMetric:
    timestamp: str
    provider: str
    model: str
    task: str
    status: str
    attempt: int
    latency_ms: int
    ttfb_ms: int | None
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    search_units: int
    estimated_cost: float | None = None
    currency: str | None = None
    pricing_version: str | None = None


class JsonlMetricSink:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, metric: ProviderCallMetric) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(asdict(metric), ensure_ascii=False, sort_keys=True)
                + "\n"
            )


def metric_recorder_from_env() -> Any | None:
    output = os.getenv("PROVIDER_METRICS_JSONL")
    if not output:
        return None
    sink = JsonlMetricSink(Path(output))
    pricing_path = os.getenv("PROVIDER_PRICING_JSON")
    catalog = (
        PricingCatalog.load(Path(pricing_path)) if pricing_path else None
    )

    def record(metric: ProviderCallMetric) -> None:
        if catalog is not None:
            estimated = catalog.estimate(
                provider=metric.provider,
                model=metric.model,
                input_tokens=metric.input_tokens,
                output_tokens=metric.output_tokens,
                search_units=metric.search_units,
            )
            metric = replace(
                metric,
                estimated_cost=estimated,
                currency=catalog.currency if estimated is not None else None,
                pricing_version=(
                    catalog.pricing_version if estimated is not None else None
                ),
            )
        sink.write(metric)

    return record


@dataclass(frozen=True, slots=True)
class PricingCatalog:
    currency: str
    pricing_version: str
    models: dict[str, dict[str, float]]

    @classmethod
    def load(cls, path: Path) -> PricingCatalog:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            currency=str(payload["currency"]),
            pricing_version=str(payload["pricing_version"]),
            models=payload["models"],
        )

    def estimate(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        search_units: int,
    ) -> float | None:
        prices = self.models.get(f"{provider}/{model}")
        if prices is None:
            return None
        cost = (
            input_tokens
            / 1_000_000
            * float(prices.get("input_per_million_tokens", 0))
            + output_tokens
            / 1_000_000
            * float(prices.get("output_per_million_tokens", 0))
            + search_units * float(prices.get("search_unit", 0))
        )
        return round(cost, 12)


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def build_provider_report(calls: list[ProviderCallMetric]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[ProviderCallMetric]] = {}
    for call in calls:
        groups.setdefault((call.provider, call.model), []).append(call)

    models: list[dict[str, Any]] = []
    for (provider, model), rows in sorted(groups.items()):
        latencies = [row.latency_ms for row in rows]
        ttfb_values = [
            row.ttfb_ms for row in rows if row.ttfb_ms is not None
        ]
        known_costs = [
            row.estimated_cost
            for row in rows
            if row.estimated_cost is not None
        ]
        models.append(
            {
                "provider": provider,
                "model": model,
                "call_count": len(rows),
                "success_count": sum(row.status == "success" for row in rows),
                "failure_count": sum(row.status != "success" for row in rows),
                "input_tokens": sum(row.input_tokens for row in rows),
                "output_tokens": sum(row.output_tokens for row in rows),
                "cached_tokens": sum(row.cached_tokens for row in rows),
                "search_units": sum(row.search_units for row in rows),
                "average_latency_ms": round(sum(latencies) / len(latencies)),
                "p95_latency_ms": _percentile(latencies, 0.95),
                "average_ttfb_ms": (
                    round(sum(ttfb_values) / len(ttfb_values))
                    if ttfb_values
                    else None
                ),
                "estimated_cost": (
                    round(sum(known_costs), 12) if known_costs else None
                ),
                "currency": next(
                    (row.currency for row in rows if row.currency), None
                ),
            }
        )
    return {"call_count": len(calls), "models": models}


def load_jsonl_metrics(path: Path) -> list[ProviderCallMetric]:
    calls: list[ProviderCallMetric] = []
    if not path.exists():
        return calls
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            calls.append(ProviderCallMetric(**json.loads(line)))
    return calls
