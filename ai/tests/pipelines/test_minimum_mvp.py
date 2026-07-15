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


def test_unreadable_registry_flag_is_confirm_needed_not_excluded():
    # 안전: 판독불가(None) 존재 플래그는 '없음(적용 제외)'이 아니라 '확인 불가'여야 한다.
    contract = {"landlord_name": "김철수", "account_holder": "김철수"}
    unread = {"mortgage_present": None, "seizure_present": None,
              "provisional_seizure_present": None, "trust_present": None, "issue_date": None}
    by_id = {r.rule_id: r for r in run_rules(contract, unread)}
    assert by_id["R03"].status == "확인 불가"  # None → 없음으로 단정 금지
    assert by_id["R04"].status == "확인 불가"
    assert by_id["R05"].status == "확인 불가"
    assert by_id["R07"].status == "확인 불가"
    # 읽고 없음(False)은 여전히 적용 제외 — 무회귀
    readable = {"mortgage_present": False, "seizure_present": False,
                "provisional_seizure_present": False, "trust_present": False, "issue_date": "2026-07-01"}
    ok = {r.rule_id: r for r in run_rules(contract, readable)}
    assert ok["R03"].status == "적용 제외" and ok["R05"].status == "적용 제외"


def test_parser_flags_none_when_registry_fully_unreadable():
    # 등기 전체 판독불가(소유자·소재지 모두) → 존재 플래그를 False로 단정하지 않고 None.
    text = ("등기사항전부증명서 (건물)\n부동산의 표시: (판독 불가)\n열람·발급일: (판독 불가)\n"
            "【갑구】\n   소유자: (판독 불가)\n【을구】\n   (판독 불가)\n")
    fields = parse_registry(text).fields
    assert fields["owner_names"] is None and fields["property_address"] is None
    assert fields["mortgage_present"] is None
    assert fields["trust_present"] is None



def test_registry_parser_keeps_only_latest_full_transfer_owner():
    text = """등기사항전부증명서
부동산의 표시: 서울특별시 가온구 나래로 1
【갑구】 소유권에 관한 사항
순위번호 1 소유권보존
  소유자: 임안전
순위번호 2 소유권이전
  소유자: 권이름
순위번호 3 소유권이전
  소유자: 오든든
【을구】 소유권 이외의 권리에 관한 사항
(기재 사항 없음)
"""
    result = parse_registry(text)
    assert result.fields["owner_names"] == ["오든든"]
    assert result.warnings == []
    by_id = {
        item.rule_id: item
        for item in run_rules({"landlord_name": "권이름"}, result.fields)
    }
    assert by_id["R01"].status == "불일치"


def test_registry_parser_restores_previous_owner_when_latest_transfer_is_cancelled():
    text = """등기사항전부증명서
부동산의 표시: 서울특별시 가온구 나래로 1
【갑구】 소유권에 관한 사항
순위번호 1 소유권보존
  소유자: 임안전
순위번호 2 소유권이전
  소유자: 권이름
순위번호 3 소유권이전
  소유자: 오든든
순위번호 4 3번 소유권이전등기 말소
【을구】 소유권 이외의 권리에 관한 사항
(기재 사항 없음)
"""
    assert parse_registry(text).fields["owner_names"] == ["권이름"]


def test_registry_parser_preserves_joint_owners_and_explicit_partial_transfer():
    text = """등기사항전부증명서
부동산의 표시: 서울특별시 가온구 나래로 1
【갑구】 소유권에 관한 사항
순위번호 1 소유권보존
  소유자: 김하나 지분 2분의 1
  소유자: 이두리 지분 2분의 1
순위번호 2 소유권일부이전
  공유자: 김하나 지분 2분의 1 중 4분의 1 이전
  소유자: 박세모 지분 4분의 1
【을구】 소유권 이외의 권리에 관한 사항
(기재 사항 없음)
"""
    result = parse_registry(text)
    assert result.fields["owner_names"] == ["김하나", "이두리", "박세모"]
    assert result.warnings == []


def test_registry_parser_applies_explicit_owner_name_correction():
    text = """등기사항전부증명서
부동산의 표시: 서울특별시 가온구 나래로 1
【갑구】 소유권에 관한 사항
순위번호 1 소유권보존
  소유자: 김하나
순위번호 2 등기명의인표시경정
  소유자 김하나를 김하늘로 경정
【을구】 소유권 이외의 권리에 관한 사항
(기재 사항 없음)
"""
    assert parse_registry(text).fields["owner_names"] == ["김하늘"]

def test_registry_parser_does_not_guess_ambiguous_partial_transfer():
    text = """등기사항전부증명서
부동산의 표시: 서울특별시 가온구 나래로 1
【갑구】 소유권에 관한 사항
순위번호 1 소유권보존
  소유자: 김하나
순위번호 2 소유권일부이전
  소유자: 박세모
【을구】 소유권 이외의 권리에 관한 사항
(기재 사항 없음)
"""
    result = parse_registry(text)
    assert result.fields["owner_names"] is None
    assert result.warnings


def test_registry_parser_does_not_treat_unordered_history_as_joint_ownership():
    text = """등기사항전부증명서
부동산의 표시: 서울특별시 가온구 나래로 1
【갑구】 소유권에 관한 사항
소유자: 과거주인
소유자: 현재주인
【을구】 소유권 이외의 권리에 관한 사항
(기재 사항 없음)
"""
    result = parse_registry(text)
    assert result.fields["owner_names"] is None
    assert result.warnings


def test_table_labels_extract_requested_contract_and_registry_fields():
    contract = """주택임대차계약서
소 재 지
(도로명주소) 가상광역시 맑음구 새싹로 136
임 대 인
주 소
가상광역시 맑음구 새싹로 136
성 명
안이름 (서명 또는 날인)
임 차 인
성 명
김임차
입금 계좌
예 금 주
안이름
"""
    registry = """등기사항전부증명서
[표제부]
표시번호
접수
소재지번, 건물명칭 및 번호
(도로명주소) 가상광역시 맑음구 새싹로 136
[갑구]
소유자: 안이름
"""

    contract_fields = parse_contract(contract).fields
    registry_fields = parse_registry(registry).fields

    assert contract_fields["landlord_name"] == "안이름"
    assert contract_fields["account_holder"] == "안이름"
    assert registry_fields["property_address"] == "(도로명주소) 가상광역시 맑음구 새싹로 136"


def test_registry_address_excludes_adjacent_building_details_and_notes():
    registry = """등기사항전부증명서
[표제부]
소재지번, 건물명칭 및 번호
(도로명주소) 가상광역시 맑음구 새싹로 136 건물내역 철근콘크리트조 84.97㎡ 등기원인 및 기타사항 2020년 1월 2일
[갑구]
소유자: 안이름
"""

    fields = parse_registry(registry).fields

    assert fields["property_address"] == "(도로명주소) 가상광역시 맑음구 새싹로 136"


def test_registry_address_stops_before_unlabeled_building_structure():
    registry = """등기사항전부증명서
[표제부]
소재지번, 건물명칭 및 번호
(도로명주소) 가상광역시 맑음구 새싹로 136 철근콘크리트조 84.97㎡
[갑구]
소유자: 안이름
"""

    fields = parse_registry(registry).fields

    assert fields["property_address"] == "(도로명주소) 가상광역시 맑음구 새싹로 136"


def test_contract_extracts_landlord_name_separated_from_signature_cell():
    contract = """주택임대차계약서
임
대
인
주 소
가상광역시 한빛구 다음로 265
주민등록번호
000000-0000000
전 화
010-0000-0000
성 명
(서명 또는 인)
안 이 름
임
차
인
성 명
김 임 차
"""

    fields = parse_contract(contract).fields

    assert fields["landlord_name"] == "안이름"
    assert fields["account_holder"] is None
