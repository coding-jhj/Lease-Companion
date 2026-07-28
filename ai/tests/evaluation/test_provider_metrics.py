from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from lease_companion_ai.evaluation.provider_metrics import (
    JsonlMetricSink,
    PricingCatalog,
    ProviderCallMetric,
    build_provider_report,
    extract_cohere_usage,
    extract_gemini_usage,
)


def test_extract_gemini_usage_reads_sdk_usage_metadata() -> None:
    response = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=120,
            candidates_token_count=30,
            cached_content_token_count=20,
            total_token_count=150,
        )
    )

    assert extract_gemini_usage(response) == {
        "input_tokens": 120,
        "output_tokens": 30,
        "cached_tokens": 20,
        "total_tokens": 150,
    }


def test_extract_cohere_usage_reads_billed_search_units() -> None:
    response = SimpleNamespace(
        meta=SimpleNamespace(
            billed_units=SimpleNamespace(search_units=2),
            tokens=SimpleNamespace(input_tokens=40, output_tokens=0),
        )
    )

    assert extract_cohere_usage(response) == {
        "input_tokens": 40,
        "output_tokens": 0,
        "search_units": 2,
    }


def test_jsonl_sink_does_not_store_prompt_or_document_content(tmp_path: Path) -> None:
    output = tmp_path / "provider-calls.jsonl"
    metric = ProviderCallMetric(
        timestamp="2026-07-28T12:00:00+00:00",
        provider="cohere",
        model="rerank-v4.0-pro",
        task="rerank",
        status="success",
        attempt=1,
        latency_ms=250,
        ttfb_ms=None,
        input_tokens=40,
        output_tokens=0,
        cached_tokens=0,
        search_units=1,
    )

    JsonlMetricSink(output).write(metric)

    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["provider"] == "cohere"
    assert "prompt" not in record
    assert "documents" not in record


def test_pricing_catalog_estimates_only_versioned_known_prices(tmp_path: Path) -> None:
    path = tmp_path / "pricing.json"
    path.write_text(
        json.dumps(
            {
                "currency": "USD",
                "pricing_version": "2026-07-28",
                "models": {
                    "gemini/test": {
                        "input_per_million_tokens": 1.0,
                        "output_per_million_tokens": 2.0,
                    },
                    "cohere/rerank-v4.0-pro": {
                        "search_unit": 0.002,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    catalog = PricingCatalog.load(path)

    assert catalog.estimate(
        provider="gemini",
        model="test",
        input_tokens=1_000_000,
        output_tokens=500_000,
        search_units=0,
    ) == 2.0
    assert catalog.estimate(
        provider="cohere",
        model="rerank-v4.0-pro",
        input_tokens=0,
        output_tokens=0,
        search_units=3,
    ) == 0.006
    assert catalog.estimate(
        provider="gemini",
        model="unknown",
        input_tokens=1,
        output_tokens=1,
        search_units=0,
    ) is None


def test_report_aggregates_model_usage_and_latency_percentiles() -> None:
    calls = [
        ProviderCallMetric(
            timestamp=f"2026-07-28T12:00:0{index}+00:00",
            provider="gemini",
            model="test",
            task="generation",
            status="success",
            attempt=1,
            latency_ms=latency,
            ttfb_ms=None,
            input_tokens=10,
            output_tokens=5,
            cached_tokens=0,
            search_units=0,
            estimated_cost=0.001,
            currency="USD",
            pricing_version="2026-07-28",
        )
        for index, latency in enumerate((100, 200, 900))
    ]

    report = build_provider_report(calls)

    row = report["models"][0]
    assert row["call_count"] == 3
    assert row["success_count"] == 3
    assert row["input_tokens"] == 30
    assert row["average_latency_ms"] == 400
    assert row["p95_latency_ms"] == 900
    assert row["average_ttfb_ms"] is None
    assert row["estimated_cost"] == 0.003
