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


def test_registry_extracts_active_ground_right_without_monetary_conversion():
    fields = parse_registry(
        """등기사항전부증명서
갑구 소유권에 관한 사항
1 소유권이전 소유자 오안심
을구 소유권 이외의 권리에 관한 사항
1 지상권설정 목적 건물 소유 범위 토지 전부 지상권자 맑음저축은행
"""
    ).fields

    assert fields["owner_shares"] == {"오안심": "1/1"}
    assert fields["ground_right_present"] is True
    assert "senior_claim_amount" not in fields


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


def test_standard_monthly_form_extracts_use_handover_contract_date_and_variable_fee_items():
    fields = parse_contract(
        """주택임대차표준계약서
☐ 전세 ☑ 월세
구조·용도 철골구조 오피스 건 물 면적 2,336.02 ㎡ 텔
보 증 금 금 10,000,000 원정 (₩ 10,000,000)
계 약 금 금 2,000,000 원정 (₩ 2,000,000)은 계약시에 지불하고 영수함.
차임(월세) 금 740,000 원정은 매월 10일에 지불한다.
관 리 비 (정액이 아닌 경우) 세대별 사용량 비례(전기·수도·가스), 세대수 비례(공용관리비)
제2조 임대인은 임차주택을 사용·수익할 수 있는 상태로 2026년 10월 2일까지 임차인에게 인도한다.
수리 완료 시기: 입주일 전날(2026년 10월 1일)까지
본 계약을 증명하기 위하여 서명한다.
2026년 10월 1일
"""
    ).fields

    assert fields["contract_type"] == "보증부월세"
    assert fields["building_use"] == "오피스텔"
    assert fields["monthly_rent"] == 740_000
    assert fields["contract_payment_date"] == "2026-10-01"
    assert fields["move_in_date"] == "2026-10-02"
    assert fields["management_fee"] is None
    assert fields["management_fee_items"] == ["전기", "수도", "가스", "공용관리비"]


def test_wrapped_period_and_bullet_special_clauses_are_joined():
    fields = parse_contract(
        """주택임대차표준계약서
제2조(임대차기간) 임대인은 2026년 10월 2일까지 임차인에게 인도하고, 임대차기간은 인도일
로부터 2028년 10월 2일까지로 한다.
제3조(입주 전 수리) 수리 사항을 정한다.
[특약사항]
• 임차인은 2026년 10월 2일까지 전입신고를 하고, 임대인은 다음날
까지 담보권을 설정할 수 없다.
• 분쟁이 있으면 조정위원회에 조정을 신청한다.
  (☐ 동의 ☑ 미동의)

본 계약을 증명하기 위하여 서명한다.
"""
    ).fields

    assert fields["start_date"] == "2026-10-02"
    assert fields["end_date"] == "2028-10-02"
    assert fields["special_clauses_present"] is True
    assert fields["special_clauses"] == [
        "• 임차인은 2026년 10월 2일까지 전입신고를 하고, 임대인은 다음날 까지 담보권을 설정할 수 없다.",
        "• 분쟁이 있으면 조정위원회에 조정을 신청한다. (☐ 동의 ☑ 미동의)",
    ]


def test_standard_form_table_amounts_and_bulletless_special_clauses():
    """2026 표준계약서 PDF: 금액 라벨과 값이 다른 줄에 오고, 특약이 불릿 없는 평문.

    - 제1조 표는 '보 증 금'/'잔 금' 라벨 줄 다음 줄에 '금 ... 원정 (₩...)' 값을 둔다.
    - 제4조 본문의 '특약사항에 따름 - ... 없음' 프로즈가 진짜 [특약사항] 헤더보다 먼저 나온다.
    - 진짜 특약은 불릿 없는 평문이며 첫 특약은 금액 줄바꿈으로 두 줄에 걸친다.
    """
    fields = parse_contract(
        """주택임대차표준계약서
☑ 전세 ☐ 월세
제1조(보증금과 차임 및 관리비) 위 부동산의 임대차에 관하여 합의에 의하여 아래와 같이 지불하기로 한다.
보 증 금
금 220,000,000 원정 (₩ 220,000,000)
계 약 금
금 22,000,000 원정 (₩ 22,000,000)은 계약시에 지불하고 영수함.
중 도 금
금 66,000,000 원정 (₩ 66,000,000)은 2026년 8월 10일
에 지불하며
잔 금
금 132,000,000 원정 (₩ 132,000,000)은 2026년 9월 5일
에 지불한다
차임(월세)
금 해당없음 원정은 매월 - 일에 지불한다
제3조(입주 전 수리) 임대인과 임차인은 다음과 같이 합의한다.
임대인부담
(본 계약은 특약사항에 따름 - 임대인부담 없음)
임차인부담
(본 계약은 특약사항에 따름 - 수리비 전액 임차인 부담)
제4조 임차인이 수선비용을 지출한 때에는 상환을 청구할 수 있다.
[특약사항]
임대차계약을 체결한 임차인은 사전에 고지하지 않은 선순위 임대차 정보가 있거나 미납한 국세‧지방세가
10,000,000 원을 초과하는 것을 확인한 경우 임대차기간이 시작하는 날까지 계약금 등을 포기하지 않고 임대차계약을 해제할 수 있다.
계약금은 어떠한 사유로도 임차인에게 반환하지 아니한다.
임대인은 새로운 임차인의 입주가 완료된 이후에 보증금을 반환한다.
※ 위 [특약사항] 중 일부는 임차인에게 불리한 불공정 조항의 예시로, 법적 효력이 없습니
다.
가상 계약서 · 교육·실습용 · TOXIC / 30
"""
    ).fields

    assert fields["deposit"] == 220_000_000
    assert fields["contract_payment"] == 22_000_000
    assert fields["balance_payment"] == 132_000_000
    assert fields["balance_payment_date"] == "2026-09-05"
    assert fields["monthly_rent"] is None  # '해당없음' → 금액 아님

    assert fields["special_clauses_present"] is True
    clauses = fields["special_clauses"]
    assert clauses[0].startswith("임대차계약을 체결한 임차인은")
    assert clauses[0].endswith("해제할 수 있다.")  # 줄바꿈된 첫 특약이 하나로 합쳐짐
    assert "계약금은 어떠한 사유로도 임차인에게 반환하지 아니한다." in clauses
    assert "임대인은 새로운 임차인의 입주가 완료된 이후에 보증금을 반환한다." in clauses
    assert not any("※" in c or "가상 계약서" in c for c in clauses)  # 고지문·워터마크 제외


def test_sorted_pdf_scrambled_payment_table_reads_balance_amount_and_date():
    """sort=True PDF 추출은 제1조 표의 중도금·잔금 금액과 라벨을 한 줄로 뒤섞는다.

    라벨('잔 금')이 금액보다 뒤에 와서 라벨 기반 매칭이 실패하므로, 제1조 안의
    마지막 '금 N원정 (₩N)은 [날짜]'(구조상 최종 지급 = 잔금)로 보완한다.
    """
    fields = parse_contract(
        """주택임대차표준계약서
☑ 전세 ☐ 월세
제1조(보증금과 차임 및 관리비) 위 부동산의 임대차에 관하여 합의에 의하여 아래와 같이 지불하기로 한다.
보 증 금 금 220,000,000 원정 (₩ 220,000,000)
계 약 금 금 22,000,000 원정 (₩ 22,000,000)은 계약시에 지불하고 영수함. 영수자 ( 서두식 인)
금 66,000,000 원정 (₩ 66,000,000)은 2026년 8월 10일 금 132,000,000 원정 (₩ 132,000,000)은 2026년 9월 5일 중 도 금 잔 금 에 지불하며 에 지불한다
차임(월세) 금 해당없음 원정은 매월 - 일에 지불한다 (입금계좌: - )
(정액인 경우) 총액 금 90,000 원정 (₩ 90,000)
관 리 비 1.일반관리비 금 20,000원 2.전기료 실비 정산
제2조(임대차기간) 임대인은 2026년 9월 5일까지 인도하고, 임대차기간은 인도일로부터 2028년 9월 5일까지로 한다.
"""
    ).fields

    assert fields["deposit"] == 220_000_000
    assert fields["contract_payment"] == 22_000_000
    assert fields["balance_payment"] == 132_000_000  # 마지막 날짜부 금액
    assert fields["balance_payment_date"] == "2026-09-05"
    assert fields["monthly_rent"] is None


def test_standard_form_special_clauses_survive_detached_pdf_bullets():
    # 실제 표준계약서 PDF 텍스트 레이어처럼 조항 문장은 먼저 나오고 불릿 글리프는
    # 서명 영역 뒤에 따로 추출될 수 있다. 불릿 위치에 의존하지 않고 6개 원문을 보존한다.
    result = parse_contract(
        """주택임대차표준계약서
[특약사항]
주택을 인도받은 임차인은 2026년 10월 2일까지 주민등록(전입신고)과 확정일자를 받기로 하고, 임대인은 다음날까지 담보권을 설정할 수 없다.
임대인이 위 특약에 위반하여 담보권을 설정한 경우 임차인은 계약을 해제 또는 해지할 수 있다.
이 경우 임대인은 특약 위반으로 인한 손해를 배상하여야 한다.
임대차계약을 체결한 임차인은 사전에 고지하지 않은 선순위 임대차 정보나
미납 또는 체납한 국세·지방세 40,000,000원을 초과하는 것을 확인한 경우
계약금을 포기하지 않고 계약을 해제할 수 있다.
주택임대차계약과 관련하여 분쟁이 있는 경우 먼저 주택임대차분쟁조정위원회에 조정을 신청한다. (□ 동의 ☑ 미동의)
주택의 철거 또는 재건축에 관한 구체적 계획 (☑ 없음 □ 있음)
상세주소가 없는 경우 임차인의 상세주소부여 신청에 대한 소유자 동의여부 (☑ 동의 □ 미동의)
본 계약을 증명하기 위하여 계약 당사자가 서명한다.
•
•
•
•
•
•
"""
    )

    clauses = result.fields["special_clauses"]
    assert result.fields["special_clauses_present"] is True
    assert len(clauses) == 6
    assert "2026년 10월 2일" in clauses[0]
    assert "해제 또는 해지" in clauses[1]
    assert "이 경우 임대인은" in clauses[1]
    assert "40,000,000원" in clauses[2]
    assert "☑ 미동의" in clauses[3]
    assert "☑ 없음" in clauses[4]
    assert "☑ 동의" in clauses[5]
    assert not result.warnings


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
