from __future__ import annotations

import json
from pathlib import Path

from lease_companion_ai.risk_patterns import attach_damage_patterns
from lease_companion_ai.schemas.unified import AnalysisRunResult, DamagePatternStatus


ROOT = Path(__file__).resolve().parents[3]


def test_case001_has_complete_ordered_damage_pattern_comparison() -> None:
    payload = json.loads(
        (ROOT / "data/sample/fixtures/case-001/analysis_run_result.json").read_text(
            encoding="utf-8"
        )
    )
    result = AnalysisRunResult.model_validate(payload)

    assert [item.pattern_id for item in result.damage_patterns] == [
        f"DP{index:02d}" for index in range(1, 9)
    ]
    assert result.damage_patterns[0].status is DamagePatternStatus.RELATED_SIGNAL
    assert all(item.reference_cases == () for item in result.damage_patterns)
    assert all("안전" not in item.reason for item in result.damage_patterns)


def test_old_analysis_payload_without_damage_patterns_remains_readable() -> None:
    payload = json.loads(
        (ROOT / "data/sample/fixtures/case-001/analysis_run_result.json").read_text(
            encoding="utf-8"
        )
    )
    payload.pop("damage_patterns")
    payload["results"] = payload["results"][:10]

    old_result = AnalysisRunResult.model_validate(payload)

    assert old_result.damage_patterns == []
    assert attach_damage_patterns(old_result).damage_patterns == []
