"""특약 카탈로그 결정론적 후보 매칭 검증 (Task 3).

매칭은 판정 입력 준비만 담당한다 — status/urgency/reason을 만들지 않고, 후보 R/J와
검색 범위(allowed_source_sections)만 고른다. 한 문장에 여러 논점이 있으면 여러 후보를
허용하되 동일 catalog_id는 중복 제거한다.
"""

from __future__ import annotations

import pytest

from lease_companion_ai.special_clauses import (
    SpecialClauseCandidate,
    load_special_clause_catalog,
    match_special_clauses,
)


def _ids(candidates, text_startswith):
    for candidate in candidates:
        if candidate.original_text.startswith(text_startswith):
            return candidate
    raise AssertionError(f"후보 없음: {text_startswith}")


def test_catalog_loads_six_draft_entries():
    catalog = load_special_clause_catalog()
    assert {entry.catalog_id for entry in catalog} >= {
        "SC-DEFERRED-REFUND",
        "SC-REPAIR-SCOPE",
        "SC-RESTORATION-SCOPE",
        "SC-RIGHTS-CHANGE",
        "SC-MANAGEMENT-FEE",
        "SC-MAIN-SPECIAL-CONFLICT",
    }


def test_pattern_match_selects_catalog_and_candidate_rj():
    (candidate,) = match_special_clauses(
        ["임대인은 새로운 임차인의 입주가 완료된 이후에 보증금을 반환한다."]
    )
    assert isinstance(candidate, SpecialClauseCandidate)
    assert candidate.catalog_ids == ("SC-DEFERRED-REFUND",)
    assert candidate.match_method == "catalog_pattern"
    assert candidate.related_judgment_ids == ("J10",)
    assert candidate.related_rule_ids == ("R08",)
    # 검색 범위는 카탈로그가 제한한 공식 출처/섹션을 그대로 전달
    assert any(s["source_id"] == "SRC-HTA-LAW" for s in candidate.allowed_source_sections)
    # 매칭은 판정 상태를 만들지 않는다
    assert not hasattr(candidate, "status")
    assert not hasattr(candidate, "urgency")


def test_exclude_pattern_blocks_exception_sentence():
    candidates = match_special_clauses(
        ["임대인은 신규 임차인 입주와 관계없이 계약 종료 시 보증금을 반환한다."]
    )
    assert candidates[0].match_method == "unmatched"
    assert candidates[0].catalog_ids == ()
    assert candidates[0].related_judgment_ids == ()


def test_unmatched_clause_returns_unmatched_candidate():
    (candidate,) = match_special_clauses(["임대차 기간은 24개월로 한다."])
    assert candidate.match_method == "unmatched"
    assert candidate.catalog_ids == ()


def test_compound_clause_yields_multiple_catalog_ids_without_duplicates():
    (candidate,) = match_special_clauses(
        [
            "임차주택의 수리에 관한 모든 비용은 임차인이 부담하며 "
            "관리비의 항목 및 금액은 임대인이 임의로 변경할 수 있다."
        ]
    )
    assert set(candidate.catalog_ids) == {"SC-REPAIR-SCOPE", "SC-MANAGEMENT-FEE"}
    assert len(candidate.catalog_ids) == len(set(candidate.catalog_ids))
    # 연결 R/J는 매칭된 유형들의 합집합(중복 제거)
    assert "R09" in candidate.related_rule_ids and "R18" in candidate.related_rule_ids
    assert "J11" in candidate.related_judgment_ids and "J09" in candidate.related_judgment_ids


def test_clause_ids_are_unique_and_deterministic():
    clauses = [
        "임대인은 새로운 임차인의 입주가 완료된 이후에 보증금을 반환한다.",
        "관리비의 항목 및 금액은 임대인이 임의로 변경할 수 있으며 임차인은 이에 따른다.",
    ]
    first = match_special_clauses(clauses)
    second = match_special_clauses(clauses)
    ids = [candidate.clause_id for candidate in first]
    assert len(ids) == len(set(ids))
    assert [c.clause_id for c in first] == [c.clause_id for c in second]


def test_uses_confirmed_text_and_normalizes_whitespace_only():
    (candidate,) = match_special_clauses(
        ["관리비의  항목 및 금액은\t임대인이 임의로 변경할 수 있으며 임차인은 이에 따른다."]
    )
    assert candidate.catalog_ids == ("SC-MANAGEMENT-FEE",)
    # 원문은 사용자 확인 값을 보존한다(정규화는 매칭에만 사용)
    assert "관리비" in candidate.original_text
