"""합성 TXT 로컬 fallback의 J01~J12 입력 추출 회귀."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lease_companion_ai.extraction.minimum_mvp import parse_contract, parse_registry
from lease_companion_ai.rules.judgments import run_judgments
from lease_companion_ai.schemas.adapters import (
    build_snapshot,
    confirm_document,
    document_from_legacy,
)
from lease_companion_ai.schemas.unified import ContractContext, build_judgment_input

ROOT = Path(__file__).resolve().parents[3]


def _contract(name: str) -> dict:
    text = (ROOT / "data" / "sample" / "contracts" / name).read_text(
        encoding="utf-8"
    )
    return parse_contract(text).fields


def test_compact_contract_extracts_j_amounts_dates_proxy_and_clauses():
    text = (
        ROOT
        / "data"
        / "evaluation"
        / "end-to-end"
        / "contracts"
        / "contract_TEST-004.txt"
    ).read_text(encoding="utf-8")

    fields = parse_contract(text).fields

    assert fields["contract_type"] == "전세"
    assert fields["property_address"] == "서울특별시 빛솔구 미쁨로 13, 131동 401호"
    assert fields["deposit"] == 500_000_000
    assert fields["monthly_rent"] is None
    assert fields["contract_payment"] == 50_000_000
    assert fields["balance_payment"] == 450_000_000
    assert fields["start_date"] == "2026-11-05"
    assert fields["end_date"] == "2028-11-04"
    assert fields["move_in_date"] == "2026-11-05"
    assert fields["agent_name"] == "길봄"
    assert fields["agent_relationship"] == "임대인 위임"
    assert fields["proxy_authority_documents"] is None
    assert fields["management_fee_present"] is False
    assert fields["deposit_return_clause"].startswith("- 보증금은")
    assert fields["repair_responsibility_clause"].startswith("- 주요 설비")
    assert fields["special_clauses_present"] is True
    assert len(fields["special_clauses"]) == 3
    assert fields["main_clauses"]


def test_form_contract_extracts_korean_amounts_management_fee_and_proxy_documents():
    fields = _contract("contract_002.txt")

    assert fields["contract_type"] == "보증부월세"
    assert fields["deposit"] == fields["deposit_korean_amount"] == 50_000_000
    assert fields["monthly_rent"] == fields["monthly_rent_korean_amount"] == 600_000
    assert fields["contract_payment"] == fields["contract_payment_korean_amount"] == 5_000_000
    assert fields["balance_payment"] == fields["balance_payment_korean_amount"] == 45_000_000
    assert fields["balance_payment_date"] == "2026-09-01"
    assert fields["start_date"] == "2026-09-01"
    assert fields["end_date"] == "2028-08-31"
    assert fields["move_in_date"] == "2026-09-01"
    assert fields["management_fee_present"] is True
    assert fields["management_fee"] == 150_000
    assert fields["management_fee_items"] == ["청소", "경비", "공용전기"]

    proxy = _contract("contract_004.txt")
    assert proxy["agent_name"] == "임재원"
    assert proxy["agent_relationship"] == "배우자"
    assert proxy["proxy_authority_documents"] == ["위임장", "인감증명서"]


def test_registry_extracts_joint_ownership_and_normalized_shares():
    text = """등기사항전부증명서
부동산의 표시: 서울특별시 가온구 나래로 1
발급일자: 2026-07-01
【갑구】 소유권에 관한 사항
순위번호 1 소유권보존
  소유자: 김하나 지분 2분의 1
  소유자: 이두리 지분 2분의 1
【을구】 소유권 이외의 권리에 관한 사항
(기재 사항 없음)
"""

    fields = parse_registry(text).fields

    assert fields["owner_names"] == ["김하나", "이두리"]
    assert fields["is_joint_ownership"] is True
    assert fields["owner_shares"] == {"김하나": "1/2", "이두리": "1/2"}


def test_flat_registry_extracts_single_owner_share_and_clean_address():
    text = (
        ROOT
        / "data"
        / "evaluation"
        / "end-to-end"
        / "registry-records"
        / "registry_TEST-004.txt"
    ).read_text(encoding="utf-8")

    fields = parse_registry(text).fields

    assert fields["owner_names"] == ["도세아"]
    assert fields["is_joint_ownership"] is False
    assert fields["owner_shares"] == {"도세아": "1/1"}
    assert fields["property_address"] == "서울특별시 빛솔구 미쁨로 13, 131동 401호"
    assert fields["issue_date"] == "2026-11-01"
    assert fields["trust_present"] is True


def test_missing_values_keep_every_j_field_without_guessing():
    fields = parse_contract("주택임대차계약서").fields

    expected = {
        "agent_name",
        "agent_relationship",
        "proxy_authority_documents",
        "deposit",
        "deposit_korean_amount",
        "monthly_rent",
        "monthly_rent_korean_amount",
        "contract_payment",
        "contract_payment_korean_amount",
        "balance_payment",
        "balance_payment_korean_amount",
        "contract_payment_date",
        "balance_payment_date",
        "move_in_date",
        "start_date",
        "end_date",
        "management_fee_present",
        "management_fee",
        "management_fee_items",
        "deposit_return_clause",
        "repair_responsibility_clause",
        "main_clauses",
        "special_clauses_present",
        "special_clauses",
    }
    assert expected <= fields.keys()
    assert fields["management_fee_present"] is False
    assert fields["special_clauses_present"] is False
    assert all(
        fields[name] is None
        for name in expected - {"management_fee_present", "special_clauses_present"}
    )


def test_korean_only_amount_and_explicit_absence_are_preserved():
    fields = parse_contract(
        """주택임대차계약서 (전세)
제1조 보증금 금 일억원정
제2조 관리비 없음
3. 특약사항 없음
"""
    ).fields

    assert fields["deposit"] is None
    assert fields["deposit_korean_amount"] == 100_000_000
    assert fields["management_fee_present"] is False
    assert fields["special_clauses_present"] is False
    assert fields["special_clauses"] is None


def test_local_fallback_builds_canonical_input_and_runs_all_judgments():
    contract_fields = _contract("contract_002.txt")
    registry_text = (
        ROOT / "data" / "sample" / "registry-records" / "registry_002.txt"
    ).read_text(encoding="utf-8")
    contract = confirm_document(
        document_from_legacy(
            {"document_type": "contract", "fields": contract_fields},
            document_id="DOC-CONTRACT-002",
        )
    )
    registry = confirm_document(
        document_from_legacy(
            {
                "document_type": "registry_record",
                "fields": parse_registry(registry_text).fields,
            },
            document_id="DOC-REGISTRY-002",
        )
    )
    context = ContractContext(
        contract_id=2,
        contract_type="보증부 월세",
        contract_stage="계약금 입금 전",
        deposit_paid=False,
        signed=False,
        move_in_date="2026-09-01",
        balance_payment_date="2026-09-01",
        is_proxy_contract=False,
    )
    snapshot = build_snapshot(
        input_snapshot_id="SNAP-CASE-002",
        contract_id=2,
        contract_context=context,
        contract_doc=contract,
        registry_doc=registry,
        confirmed_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
        case_id="CASE-002",
    )

    results = run_judgments(build_judgment_input(snapshot))

    assert [result.judgment_id for result in results] == [
        f"J{index:02d}" for index in range(1, 13)
    ]
    assert {result.judgment_id: result.status.value for result in results} == {
        "J01": "일치",
        "J02": "일치",
        "J03": "적용 제외",
        "J04": "적용 제외",
        "J05": "일치",
        "J06": "명확",
        "J07": "일치",
        "J08": "일치",
        "J09": "명확",
        "J10": "명확",
        "J11": "명확",
        "J12": "확인 필요",
    }
