from pathlib import Path

from lease_companion_ai.extraction.minimum_mvp import parse_contract, parse_registry
from lease_companion_ai.pipelines.minimum_mvp import (
    _repair_contract_provider_fields,
    _structure_unified,
    analyze_verified_fields,
    extract_documents,
)
from lease_companion_ai.rules.minimum_mvp import run_rules
from lease_companion_ai.schemas.unified import (
    ContractContext,
    DocumentExtraction,
    VerificationStatus,
)


ROOT = Path(__file__).resolve().parents[3]


def test_contract_provider_nulls_are_repaired_without_overwriting_provider_values():
    repaired, warnings = _repair_contract_provider_fields(
        {
            "bank_name": "제공자은행",
            "balance_payment": None,
            "balance_payment_date": None,
            "end_date": None,
            "special_clauses_present": None,
            "special_clauses": None,
        },
        """주택임대차표준계약서
잔 금 금 8,000,000원은 2026년 2월 13일에 지불한다.
차임은 매월 지급한다 (입금계좌: 가상은행 804-71-336785)
제2조(임대차기간) 2026년 10월 2일부터 임대차기간은
2028년 10월 2일까지로 한다.
[특약사항]
• 임대인은 다음날까지 담보권을 설정할 수 없다.
""",
    )

    assert repaired["bank_name"] == "제공자은행"
    assert repaired["balance_payment"] == 8_000_000
    assert repaired["balance_payment_date"] == "2026-02-13"
    assert repaired["end_date"] == "2028-10-02"
    assert repaired["special_clauses"] == ["• 임대인은 다음날까지 담보권을 설정할 수 없다."]
    assert any("balance_payment" in warning for warning in warnings)


def test_contract_provider_explicit_absence_is_not_replaced_with_local_content():
    repaired, _ = _repair_contract_provider_fields(
        {
            "management_fee_present": False,
            "management_fee": None,
            "management_fee_items": None,
            "special_clauses_present": False,
            "special_clauses": None,
        },
        """주택임대차표준계약서
관리비 월 100,000원(청소·경비)
[특약사항]
• 임대인은 다음날까지 담보권을 설정할 수 없다.
""",
    )

    assert repaired["management_fee_present"] is False
    assert repaired["management_fee"] is None
    assert repaired["management_fee_items"] is None
    assert repaired["special_clauses_present"] is False
    assert repaired["special_clauses"] is None


def test_contract_provider_partial_special_clauses_are_replaced_with_full_local_text():
    repaired, warnings = _repair_contract_provider_fields(
        {
            "special_clauses_present": True,
            "special_clauses": ["임대인은 담보권을 설정하지 않는다."],
        },
        """주택임대차표준계약서
[특약사항]
주택을 인도받은 임차인은 확정일자를 받고, 임대인은 다음날까지 담보권을 설정할 수 없다.
임대인이 위 특약에 위반한 경우 임차인은 계약을 해제 또는 해지할 수 있다.
주택의 철거 또는 재건축에 관한 구체적 계획 (☑ 없음 □ 있음)
본 계약을 증명하기 위하여 서명한다.
""",
    )

    assert len(repaired["special_clauses"]) == 3
    assert "확정일자" in repaired["special_clauses"][0]
    assert "해제 또는 해지" in repaired["special_clauses"][1]
    assert "☑ 없음" in repaired["special_clauses"][2]
    assert any("일부만 반환한 특약" in warning for warning in warnings)


def test_swapped_documents_are_flagged_with_guidance():
    # 계약서 자리에 등기부, 등기부 자리에 계약서를 넣은 경우 — 빈 추출값 대신 안내를 낸다.
    contract = (ROOT / "data/sample/contracts/contract_001.txt").read_bytes()
    registry = (ROOT / "data/sample/registry-records/registry_001.txt").read_bytes()

    out = extract_documents(registry, "registry.txt", contract, "contract.txt")

    assert out["contract"]["read_ok"] is False
    assert "등기사항증명서" in out["contract"]["error"] and "확인" in out["contract"]["error"]
    assert out["registry"]["read_ok"] is False
    assert "계약서" in out["registry"]["error"]


def test_swapped_registry_with_spaced_pdf_title_is_flagged_in_contract_slot():
    # 실제 PDF 텍스트 레이어는 제목이 "등 기 사 항 전 부 증 명 서"처럼 글자 간 공백으로 나온다.
    registry_text = """등 기 사 항 전 부 증 명 서
(말소사항 포함)갑구 소유권에 관한 사항
1 소유권보존 소유자 윤든든
""".encode("utf-8")
    contract = (ROOT / "data/sample/contracts/contract_001.txt").read_bytes()

    out = extract_documents(registry_text, "registry.txt", contract, "contract.txt")

    assert out["contract"]["read_ok"] is False
    assert "등기사항증명서" in out["contract"]["error"]


def test_correct_documents_are_not_flagged_as_swapped():
    contract = (ROOT / "data/sample/contracts/contract_001.txt").read_bytes()
    registry = (ROOT / "data/sample/registry-records/registry_001.txt").read_bytes()

    out = extract_documents(contract, "contract.txt", registry, "registry.txt")

    assert out["contract"]["read_ok"] is True
    assert out["registry"]["read_ok"] is True


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


def test_rules_return_all_twenty_four_results_without_safety_score():
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

    assert len(results) == 24
    assert [result.rule_id for result in results] == [f"R{i:02d}" for i in range(1, 25)]
    assert by_id["R01"].status == "불일치"
    assert by_id["R02"].status == "일치"
    assert by_id["R03"].status == "확인 필요"
    assert by_id["R05"].status == "적용 제외"
    assert not any("사기 가능성 점수" in result.reason for result in results)


def test_rule_engine_never_exposes_static_source_map(monkeypatch):
    from lease_companion_ai.rules import minimum_mvp as rules

    real_read = rules._read_csv

    def fake_read(name):
        if name != "source_inventory.csv":
            return real_read(name)
        common = {"title": "자료", "institution": "공식기관", "summary": "요약"}
        return [
            {**common, "source_id": "SRC-STD-LEASE", "source_status": "official_verified", "source_url": "https://official.example/source"},
            {**common, "source_id": "SRC-REGISTRY-SAMPLE", "source_status": "synthetic_reference", "source_url": "https://example.invalid/sample"},
            {**common, "source_id": "SRC-MOLIT-CHECKLIST", "source_status": "unverified", "source_url": "https://official.example/unverified"},
            {**common, "source_id": "SRC-CONFIRM-FORM", "source_status": "excluded", "source_url": "https://official.example/excluded"},
        ]

    monkeypatch.setattr(rules, "_read_csv", fake_read)
    results = rules.run_rules({}, {})
    sources = {source.source_id for result in results for source in result.evidence_sources}

    assert sources == set()


def test_rule_engine_status_and_urgency_do_not_depend_on_evidence():
    from lease_companion_ai.rules import minimum_mvp as rules

    contract = {"landlord_name": "임대인", "account_holder": "다른이", "deposit_return_condition": "명확", "repair_responsibility": "명확", "rights_change_clause_present": True}
    registry = {"owner_names": ["소유자"], "mortgage_present": True, "seizure_present": False, "provisional_seizure_present": False, "trust_present": False, "issue_date": "2026-07-01"}
    baseline = [(item.rule_id, item.status, item.urgency) for item in rules.run_rules(contract, registry)]
    without_evidence = rules.run_rules(contract, registry)

    assert [(item.rule_id, item.status, item.urgency) for item in without_evidence] == baseline
    assert all(item.evidence_sources == [] for item in without_evidence)


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


def test_gemini_field_shape_feeds_run_rules():
    # Gemini 구조화 출력(스키마 필드)이 run_rules 계약을 지키는지 — tri-state·enum 포함. (API 미호출)
    from lease_companion_ai.extraction.gemini_extractor import ContractFields, RegistryFields

    contract = ContractFields(
        contract_type="전세", landlord_name="김민준", tenant_name="이임차", agent_name=None,
        property_address="서울특별시 샘플구 202호", deposit=100000000, monthly_rent=None,
        contract_payment=10000000, balance_payment=90000000, account_holder="김민준",
        start_date="2026-08-01", end_date="2028-07-31", move_in_date="2026-08-01",
        deposit_return_condition="명확", repair_responsibility="명확", rights_change_clause_present=True,
    ).model_dump()
    registry = RegistryFields(
        owner_names=["김민준"], is_joint_ownership=False, property_address="서울특별시 샘플구 202호",
        issue_date="2026-07-01", mortgage_present=None, seizure_present=False,
        provisional_seizure_present=False, trust_present=None,
    ).model_dump()

    by_id = {r.rule_id: r for r in run_rules(contract, registry)}
    assert len(by_id) == 24
    assert by_id["R01"].status == "일치"        # landlord ∈ owners
    assert by_id["R03"].status == "확인 불가"    # mortgage_present=None (tri-state)
    assert by_id["R05"].status == "확인 불가"    # trust_present=None
    assert by_id["R08"].status == "명확"         # enum 값 그대로 status


def test_v19_null_condition_fields_degrade_r08_r09_to_check_needed():
    # §8-Q1 (가) 확정: v1.9 extraction은 deposit_return_condition·repair_responsibility를
    # null로 반환한다. 그러면 legacy R08·R09는 단정하지 않고 "확인 필요"로 내려가고,
    # 실제 clarity 판정은 J10·J11(classification 후보 경유)이 소유한다. 구 필드를 다시
    # legacy에 섞지 않는다(ADR 2026-07-18, BC_JOINT_REPLY §5·§8-Q1).
    contract = {
        "landlord_name": "이정훈",
        "property_address": "서울특별시 가온구 나래로 12, 305동 1201호",
        "account_holder": "이정훈",
        "deposit_return_condition": None,   # v1.9: 해석 후보 미생성
        "repair_responsibility": None,      # v1.9: 해석 후보 미생성
        "deposit_return_clause": "보증금은 계약 종료 시 반환한다.",
        "repair_responsibility_clause": "수리는 협의하여 정한다.",
        "rights_change_clause_present": True,
    }
    registry = {
        "owner_names": ["이정훈"],
        "property_address": "서울특별시 가온구 나래로 12, 305동 1201호",
        "issue_date": "2026-07-01",
        "mortgage_present": False,
        "seizure_present": False,
        "provisional_seizure_present": False,
        "trust_present": False,
    }
    by_id = {r.rule_id: r for r in run_rules(contract, registry)}
    assert by_id["R08"].status == "확인 필요"
    assert by_id["R09"].status == "확인 필요"
    # 단정 금지 — 명확/불명확으로 넘겨짚지 않는다.
    assert by_id["R08"].status not in {"명확", "불명확"}
    assert by_id["R09"].status not in {"명확", "불명확"}


def test_structure_falls_back_to_regex(monkeypatch):
    # 키 없음·API 실패(GeminiExtractError) 시 정규식 파서로 폴백. (API 미호출)
    from lease_companion_ai.extraction.gemini_extractor import GeminiExtractError
    from lease_companion_ai.pipelines import minimum_mvp as pipe

    def _raise(_text):
        raise GeminiExtractError("no key")

    monkeypatch.setattr(pipe, "extract_contract_fields", _raise)
    text = (ROOT / "data/sample/contracts/contract_001.txt").read_text(encoding="utf-8")
    decisions = []
    result = pipe._structure(text, "contract", routing_decisions=decisions)
    assert result["document_type"] == "contract"
    assert result["fields"]["landlord_name"] == "이정훈"  # 정규식 파서 폴백 동작
    assert decisions[0].selected.value == "local_regex"
    assert decisions[0].failure_reason.value == "provider_error"


def test_actual_structure_path_builds_canonical_document(monkeypatch):
    from lease_companion_ai.pipelines import minimum_mvp as pipe

    def _raise(_text):
        raise pipe.GeminiExtractError("no key")

    monkeypatch.setattr(pipe, "extract_contract_fields", _raise)
    text = (ROOT / "data/sample/contracts/contract_001.txt").read_text(encoding="utf-8")
    result = _structure_unified(text, "contract", document_id="DOC-1")

    assert isinstance(result, DocumentExtraction)
    assert result.document_id == "DOC-1"
    assert result.fields["landlord_name"].verification_status is VerificationStatus.UNVERIFIED


def test_gemini_success_shape_also_builds_canonical_document(monkeypatch):
    from lease_companion_ai.pipelines import minimum_mvp as pipe

    expected = parse_contract(
        (ROOT / "data/sample/contracts/contract_001.txt").read_text(encoding="utf-8")
    ).fields
    monkeypatch.setattr(pipe, "extract_contract_fields", lambda _text: expected)

    decisions = []
    result = _structure_unified(
        "주택임대차계약서",
        "contract",
        document_id="DOC-GEMINI",
        routing_decisions=decisions,
    )

    assert isinstance(result, DocumentExtraction)
    assert result.document_id == "DOC-GEMINI"
    assert result.fields["landlord_name"].extracted_value == "이정훈"
    assert decisions[0].selected.value == "gemini_3_5_flash"
    assert decisions[0].fallback_used is False


def test_gemini_registry_null_ownership_is_repaired_when_local_owner_matches(monkeypatch):
    from lease_companion_ai.pipelines import minimum_mvp as pipe

    monkeypatch.setattr(
        pipe,
        "extract_registry_fields",
        lambda _text: {
            "owner_names": ["오안심"],
            "is_joint_ownership": False,
            "owner_shares": None,
            "property_address": "가상광역시 이룸구 미래로 6 제1005호",
            "issue_date": "2026-07-14",
            "mortgage_present": False,
            "seizure_present": False,
            "provisional_seizure_present": False,
            "trust_present": False,
            "ground_right_present": None,
        },
    )
    text = """등기사항전부증명서
갑구 소유권에 관한 사항
1 소유권이전 소유자 오안심
을구 소유권 이외의 권리에 관한 사항
1 지상권설정 목적 건물 소유 범위 토지 전부 지상권자 맑음저축은행
"""

    result = _structure_unified(text, "registry", document_id="DOC-REGISTRY-REPAIR")

    assert result.fields["owner_shares"].extracted_value == {"오안심": "1/1"}
    assert result.fields["ground_right_present"].extracted_value is True
    assert any("결정론적 등기 파서" in warning for warning in result.warnings)


def test_verified_legacy_analysis_uses_canonical_result_contract():
    contract = parse_contract(
        (ROOT / "data/sample/contracts/contract_001.txt").read_text(encoding="utf-8")
    ).fields
    registry = parse_registry(
        (ROOT / "data/sample/registry-records/registry_001.txt").read_text(encoding="utf-8")
    ).fields

    results = analyze_verified_fields(
        contract,
        registry,
        ContractContext(
            contract_id=1,
            contract_type="전세",
            contract_stage="계약금 입금 전",
            deposit_paid=False,
            signed=False,
            is_proxy_contract=False,
        ),
    )

    assert [result["rule_id"] for result in results] == [f"R{i:02d}" for i in range(1, 25)]
    assert all(set(result) == {
        "rule_id", "rule_name", "judgment_id", "status", "urgency", "reason",
        "result_type", "triggers_actions", "question", "recommended_actions",
        "evidence_sources", "limitations", "completed",
    } for result in results)
    direct_contract = {**contract, "is_proxy_contract": False}
    legacy_results = [result.to_dict() for result in run_rules(direct_contract, registry)]
    for result, legacy in zip(results, legacy_results, strict=True):
        comparable = {
            key: value
            for key, value in result.items()
            if key not in {"result_type", "triggers_actions", "evidence_sources"}
        }
        assert comparable == {key: value for key, value in legacy.items() if key != "evidence_sources"}
        assert legacy["evidence_sources"] == []
        assert all(source["source_id"].startswith("SRC-") for source in result["evidence_sources"])


def test_extended_rules_calculate_inputs_and_keep_deferred_rules_honest():
    contract = {
        "deposit": 180_000_000,
        "estimated_housing_value": 300_000_000,
        "is_proxy_contract": True,
        "proxy_authority_documents": ["위임장", "인감증명서"],
        "building_use": "공동주택",
        "violation_building": False,
        "guarantee_eligibility_confirmed": True,
        "lessor_sublease_authority_confirmed": False,
        "management_fee_present": True,
        "management_fee": 120_000,
        "management_fee_items": ["일반관리비", "수도료"],
        "rights_change_clause_present": True,
    }
    registry = {"senior_claim_amount": 60_000_000}

    by_id = {result.rule_id: result for result in run_rules(contract, registry)}

    assert "60.0%" in by_id["R11"].reason
    assert "60,000,000원" in by_id["R12"].reason
    assert by_id["R13"].status == "명확"
    assert by_id["R14"].status == "명확"
    assert by_id["R15"].status == "명확"
    assert by_id["R16"].status == "확인 필요"
    assert by_id["R17"].status == "확인 필요"
    assert by_id["R18"].status == "명확"
    assert by_id["R19"].status == "명확"
    assert {by_id[rule_id].status for rule_id in ("R20", "R21", "R22")} == {"확인 불가"}
    assert {by_id[rule_id].status for rule_id in ("R23", "R24")} == {"확인 필요"}

    not_applicable = {
        result.rule_id: result
        for result in run_rules(
            {"is_proxy_contract": False, "management_fee_present": False},
            {},
        )
    }
    assert not_applicable["R13"].reason == "대리계약이 아닌 것으로 입력되어 이 항목은 적용하지 않습니다."
    assert not_applicable["R18"].reason == "관리비가 없는 것으로 입력되어 이 항목은 적용하지 않습니다."


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
    assert registry_fields["property_address"] == "가상광역시 맑음구 새싹로 136"


def test_account_number_and_bank_extracted_without_account_holder():
    # 예금주 없이 계좌번호·은행명만 적힌 계약서 — 예금주 null이어도 나머지는 추출된다.
    contract = """주택임대차계약서
임 대 인
성 명 안이름
입금 계좌
신한은행 110-234-567890
"""
    fields = parse_contract(contract).fields
    assert fields["account_number"] == "110-234-567890"
    assert fields["bank_name"] == "신한은행"
    assert fields["account_holder"] is None


def test_special_clauses_extracts_unicode_bullets_and_wrapped_lines():
    # 표준계약서는 • (U+2022) 불릿을 쓰고 PDF 추출 시 특약이 여러 줄로 쪼개진다.
    contract = """주택임대차계약서
[특약사항]
• 임대인은 잔금일 다음 날까지 임차주택에 근저당권을
설정하지 않는다.
• 분쟁이 있는 경우 조정위원회에 조정을 신청한다.
임대인 성명 안이름 (서명 또는 날인)
"""
    fields = parse_contract(contract).fields
    assert fields["special_clauses_present"] is True
    special = fields["special_clauses"]
    assert len(special) == 2
    assert "설정하지 않는다" in special[0]  # 줄바꿈으로 쪼개진 줄이 이어붙었는지
    assert "조정위원회" in special[1]
    assert "서명" not in " ".join(special)  # 서명 블록은 포함하지 않는다


def test_registry_address_excludes_adjacent_building_details_and_notes():
    registry = """등기사항전부증명서
[표제부]
소재지번, 건물명칭 및 번호
(도로명주소) 가상광역시 맑음구 새싹로 136 건물내역 철근콘크리트조 84.97㎡ 등기원인 및 기타사항 2020년 1월 2일
[갑구]
소유자: 안이름
"""

    fields = parse_registry(registry).fields

    assert fields["property_address"] == "가상광역시 맑음구 새싹로 136"


def test_contract_address_excludes_location_and_road_address_labels():
    contract = """주택임대차계약서
소 재 지 [도로명주소] 가상광역시 안전구 이룸로 18층 공동주택 138
임 대 인
성 명 안이름
"""

    fields = parse_contract(contract).fields

    assert fields["property_address"] == "가상광역시 안전구 이룸로 18층 공동주택 138"


def test_registry_address_excludes_document_number_and_effect_cell():
    registry = """등기사항전부증명서 [표제부]
소재지번, 건물명칭 및 번호
제 19402호 [도로명주소] 가상광역시 안전구 이룸로 18층 공동주택 138 1층 258.62효력
[갑구]
소유자: 안이름
"""

    fields = parse_registry(registry).fields

    assert fields["property_address"] == "가상광역시 안전구 이룸로 18층 공동주택 138"


def test_registry_address_stops_before_unlabeled_building_structure():
    registry = """등기사항전부증명서
[표제부]
소재지번, 건물명칭 및 번호
(도로명주소) 가상광역시 맑음구 새싹로 136 철근콘크리트조 84.97㎡
[갑구]
소유자: 안이름
"""

    fields = parse_registry(registry).fields

    assert fields["property_address"] == "가상광역시 맑음구 새싹로 136"


def test_registry_rank_rows_merged_into_one_line_still_apply_ownership_history():
    # PyMuPDF sort=True가 '효력' 열 셀과 다음 순위 행을 앞 행 끝에 이어붙인 실제 레이아웃.
    # 순위 2(이전)가 줄 중간에 있어도 이력을 적용해 현재 소유자만 남겨야 한다.
    registry = """등기사항전부증명서
(말소사항 포함)갑구 소유권에 관한 사항       없음
순위번호    등기목적       접수        등기원인               권리자 및 기타사항         효력
1   소유권보존        2022년 8월 28일  2022년 8월 25일      소유자 윤든든 900804-1******
제37245호                  가상광역시 금융로 68       법적        ·    2   소유권이전        2024년 5월 27일  2024년 2월 28일      소유자 강안전 730401-2******
제10013호    매매           가상광역시 데이터로 59
3   압류            2026년 11월 11   2026년 7월 18일      권리자 가상세무서     등기부                일          압류(체납처분)
제10014호   모의
— 이 하 여 백 —
"""

    fields = parse_registry(registry).fields

    assert fields["owner_names"] == ["강안전"]
    assert fields["seizure_present"] is True


def test_registry_owner_mention_before_first_rank_entry_returns_unresolved():
    # 순위 항목으로 안 잡힌 구간에 소유자가 남아 있으면 확정하지 말고 직접 확인을 요구해야 한다.
    registry = """등기사항전부증명서
[갑구]
소유자 윤든든 900804-1******
2   소유권이전   2024년 5월 27일   매매   소유자 강안전
"""

    result = parse_registry(registry)

    assert result.fields["owner_names"] is None
    assert any("직접 확인" in warning for warning in result.warnings)


def test_contract_extracts_tenant_name_from_signature_line():
    contract = (ROOT / "data/sample/contracts/contract_001.txt").read_text(encoding="utf-8")

    fields = parse_contract(contract).fields

    assert fields["tenant_name"] == "강해린"


def test_contract_extracts_tenant_name_from_table_layout():
    contract = """주택임대차계약서
임
대
인
성 명
안 이 름
임
차
인
성 명
김 임 차
"""

    fields = parse_contract(contract).fields

    assert fields["tenant_name"] == "김임차"


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
