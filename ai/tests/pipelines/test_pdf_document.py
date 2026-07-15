import fitz

from lease_companion_ai.pipelines.minimum_mvp import extract_documents


def _pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_textbox(
        fitz.Rect(40, 40, 555, 802),
        text,
        fontsize=10,
        fontname="korea",
    )
    payload = document.tobytes()
    document.close()
    return payload


def test_digital_pdf_text_layer_is_extracted_end_to_end():
    contract = _pdf_bytes(
        "주택임대차계약서\n"
        "소재지: 서울특별시 가온구 나래로 12, 305동 1201호\n"
        "보증금은 임대차 종료 및 목적물 인도와 동시에 임대인이 반환한다.\n"
        "수리는 임대인이 부담하고 원상복구는 임차인이 부담한다.\n"
        "임대인은 추가 담보권을 설정하지 않는다.\n"
        "예금주: 이정훈 / 은행\n임대인: 이정훈 (서명)"
    )
    registry = _pdf_bytes(
        "등기사항전부증명서\n"
        "소재지: 서울특별시 가온구 나래로 12, 305동 1201호\n"
        "소유자: 이정훈\n근저당권설정\n열람일시: 2026년 7월 28일"
    )

    extraction = extract_documents(contract, "contract.pdf", registry, "registry.pdf")

    assert extraction["contract"]["fields"]["landlord_name"] == "이정훈"
    assert extraction["registry"]["fields"]["owner_names"] == ["이정훈"]
    assert extraction["registry"]["fields"]["mortgage_present"] is True


def test_table_style_contract_extracts_landlord_and_property_address():
    contract = _pdf_bytes(
        "주택임대차계약서\n"
        "임차주택의 표시\n"
        "소 재 지\n"
        "서울특별시 가온구 나래로 12, 305동 1201호\n"
        "임 대 인\n"
        "성 명\n"
        "홍길동\n"
        "임 차 인\n"
        "성 명\n"
        "김임차"
    )
    registry = _pdf_bytes(
        "등기사항전부증명서\n"
        "소재지: 서울특별시 가온구 나래로 12, 305동 1201호\n"
        "소유자: 홍길동"
    )

    extraction = extract_documents(contract, "contract.pdf", registry, "registry.pdf")
    fields = extraction["contract"]["fields"]

    assert fields["landlord_name"] == "홍길동"
    assert fields["property_address"] == "서울특별시 가온구 나래로 12, 305동 1201호"
