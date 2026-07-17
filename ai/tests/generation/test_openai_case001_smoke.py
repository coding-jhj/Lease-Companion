"""명시적 승인 환경에서만 실행하는 합성 CASE-001 OpenAI smoke test."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lease_companion_ai.generation.service import GenerationService
from lease_companion_ai.providers.openai_generation import OpenAIGenerationProvider
from lease_companion_ai.schemas.unified import AnalysisRunResult


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_OPENAI_SMOKE") != "1",
    reason="RUN_OPENAI_SMOKE=1인 승인된 유료 smoke 실행에서만 호출합니다.",
)


def test_case001_openai_generation_smoke():
    fixture = Path("data/sample/fixtures/case-001/analysis_run_result.json")
    analysis = AnalysisRunResult.model_validate_json(fixture.read_text(encoding="utf-8"))
    provider = OpenAIGenerationProvider(max_calls=10, max_output_tokens=1_500)

    result = GenerationService(provider).generate(analysis)

    assert result.analysis_run_id == analysis.analysis_run_id
    assert result.guardrail_passed is True
    assert result.items
    assert all(item.rule_id.startswith("R") for item in result.items)
