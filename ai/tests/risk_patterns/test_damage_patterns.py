from __future__ import annotations

import json
from pathlib import Path

from lease_companion_ai.risk_patterns import (
    attach_damage_patterns,
    load_verified_reference_cases,
    search_reference_cases,
)
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    DamagePatternStatus,
    RuleStatus,
)


ROOT = Path(__file__).resolve().parents[3]


def _fixture_without_patterns() -> AnalysisRunResult:
    payload = json.loads(
        (ROOT / "data/sample/fixtures/case-001/analysis_run_result.json").read_text(
            encoding="utf-8"
        )
    )
    payload["damage_patterns"] = []
    return AnalysisRunResult.model_validate(payload)


def _replace_status(
    analysis: AnalysisRunResult,
    *,
    result_id: str,
    status: str,
    reason: str,
) -> AnalysisRunResult:
    parsed_status = RuleStatus(status)
    is_judgment = result_id.startswith("J")
    collection_name = "judgments" if is_judgment else "results"
    id_name = "judgment_id" if is_judgment else "rule_id"
    collection = getattr(analysis, collection_name)
    updated = [
        item.model_copy(
            update={
                "status": parsed_status,
                "reason": reason,
                "triggers_actions": parsed_status
                not in {
                    RuleStatus.MATCH,
                    RuleStatus.CLEAR,
                    RuleStatus.NOT_APPLICABLE,
                },
            }
        )
        if getattr(item, id_name) == result_id
        else item
        for item in collection
    ]
    return AnalysisRunResult.model_validate(
        analysis.model_copy(update={collection_name: updated}).model_dump()
    )


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
    assert all(
        item.reference_cases
        for item in result.damage_patterns
        if item.status is not DamagePatternStatus.NO_SIGNAL_IN_SUBMITTED_DOCS
    )
    assert all(
        item.reference_cases == ()
        for item in result.damage_patterns
        if item.status is DamagePatternStatus.NO_SIGNAL_IN_SUBMITTED_DOCS
    )
    assert all("안전" not in item.reason for item in result.damage_patterns)


def test_verified_reference_catalog_covers_all_damage_patterns() -> None:
    entries = load_verified_reference_cases()

    assert len({entry.reference_case.reference_case_id for entry in entries}) == len(entries)
    for pattern_id in (f"DP{index:02d}" for index in range(1, 9)):
        cases = search_reference_cases(pattern_id)
        assert cases
        assert all(item.source_url.startswith("https://") for item in cases)
        assert all(item.verification_scope for item in cases)


def test_dp04_separates_detected_mortgage_from_unknown_excessiveness() -> None:
    result = attach_damage_patterns(_fixture_without_patterns())
    mortgage = next(item for item in result.damage_patterns if item.pattern_id == "DP04")

    assert mortgage.status is DamagePatternStatus.RELATED_SIGNAL
    assert "근저당 설정: 관련 확인 신호 발견" in mortgage.reason
    assert "과도한 근저당 여부: 추가 확인 필요" in mortgage.reason
    assert "주택가치와 실제 선순위 금액 자료가 부족" in mortgage.reason


def test_dp04_has_no_submitted_signal_when_mortgage_is_not_applicable() -> None:
    analysis = _replace_status(
        _fixture_without_patterns(),
        result_id="R03",
        status="적용 제외",
        reason="근저당권 관련 활성 기재가 탐지되지 않았습니다.",
    )
    result = attach_damage_patterns(analysis)
    mortgage = next(item for item in result.damage_patterns if item.pattern_id == "DP04")

    assert mortgage.status is DamagePatternStatus.NO_SIGNAL_IN_SUBMITTED_DOCS


def test_dp05_marks_detected_trust_registration_as_related_signal() -> None:
    analysis = _replace_status(
        _fixture_without_patterns(),
        result_id="R05",
        status="확인 필요",
        reason="신탁 관련 활성 기재가 확인되어 계약 권한 확인이 필요합니다.",
    )
    result = attach_damage_patterns(analysis)
    trust = next(item for item in result.damage_patterns if item.pattern_id == "DP05")

    assert trust.status is DamagePatternStatus.RELATED_SIGNAL


def test_dp08_maps_deferred_refund_condition_to_related_signal() -> None:
    analysis = _replace_status(
        _fixture_without_patterns(),
        result_id="J10",
        status="확인 필요",
        reason=(
            "보증금 반환이 신규 임차인의 입주에 연동된 조건이 확인되어 "
            "반환 조건의 수정 여부를 확인해야 합니다."
        ),
    )
    result = attach_damage_patterns(analysis)
    refund = next(item for item in result.damage_patterns if item.pattern_id == "DP08")

    assert refund.status is DamagePatternStatus.RELATED_SIGNAL
    assert [item.reference_case_id for item in refund.reference_cases] == [
        "REF-HUG-DEPOSIT-NONRETURN",
        "REF-REB-ADR-2022-31",
    ]


def test_dp08_keeps_unclassified_refund_clause_as_cannot_assess() -> None:
    analysis = _replace_status(
        _fixture_without_patterns(),
        result_id="J10",
        status="확인 필요",
        reason="분류 후보를 확정할 수 없어 추가 확인이 필요합니다.",
    )
    result = attach_damage_patterns(analysis)
    refund = next(item for item in result.damage_patterns if item.pattern_id == "DP08")

    assert refund.status is DamagePatternStatus.CANNOT_ASSESS


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
