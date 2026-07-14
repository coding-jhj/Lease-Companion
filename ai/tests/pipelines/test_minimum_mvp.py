from pathlib import Path

from lease_companion_ai.extraction.minimum_mvp import parse_contract, parse_registry
from lease_companion_ai.rules.minimum_mvp import run_rules


ROOT = Path(__file__).resolve().parents[3]


def test_sample_case_001_extracts_core_fields():
    contract = (ROOT / "data/sample/contracts/contract_001.txt").read_text(encoding="utf-8")
    registry = (ROOT / "data/sample/registry-records/registry_001.txt").read_text(encoding="utf-8")

    contract_fields = parse_contract(contract).fields
    registry_fields = parse_registry(registry).fields

    assert contract_fields["landlord_name"] == "이정훈"
    assert contract_fields["account_holder"] == "이정훈"
    assert contract_fields["deposit_return_condition"] == "명확"
    assert registry_fields["owner_names"] == ["박성우"]
    assert registry_fields["mortgage_present"] is True
    assert registry_fields["seizure_present"] is False


def test_rules_return_all_ten_results_without_safety_score():
    contract = {
        "landlord_name": "이정훈",
        "property_address": "서울특별시 가온구 나래로 12, 305동 1201호",
        "account_holder": "이정훈",
        "deposit_return_condition": "명확",
        "repair_responsibility": "명확",
        "rights_change_clause_present": True,
    }
    registry = {
        "owner_names": ["박성우"],
        "property_address": "서울특별시 가온구 나래로 12, 305동 1201호",
        "issue_date": "2026-07-28",
        "mortgage_present": True,
        "seizure_present": False,
        "provisional_seizure_present": False,
        "trust_present": False,
    }

    results = run_rules(contract, registry)
    by_id = {result.rule_id: result for result in results}

    assert len(results) == 10
    assert by_id["R01"].status == "불일치"
    assert by_id["R02"].status == "일치"
    assert by_id["R03"].status == "확인 필요"
    assert by_id["R05"].status == "적용 제외"
    assert not any("사기 가능성 점수" in result.reason for result in results)


def test_registry_parser_handles_colon_format():
    # 생성 데이터(CASE-006~)는 "소유자: 이름" 콜론 표기 — 통합 파서가 처리해야 한다.
    registry = (ROOT / "data/sample/registry-records/registry_CASE-006.txt").read_text(encoding="utf-8")
    assert parse_registry(registry).fields["owner_names"] == ["강지훈"]


def test_unanalyzable_rule_avoids_fired_wording():
    # 등기 소유자를 못 읽으면 R01은 확인 불가 — 불일치 문구·즉시 확인을 붙이지 않는다.
    by_id = {r.rule_id: r for r in run_rules({"landlord_name": "김철수", "account_holder": "김철수"}, {"owner_names": None})}
    assert by_id["R01"].status == "확인 불가"
    assert by_id["R01"].urgency == "분석 불가"
    assert "다르" not in by_id["R01"].reason
    assert by_id["R01"].question is None
