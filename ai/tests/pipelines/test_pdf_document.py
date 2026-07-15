import fitz
import pytest

from lease_companion_ai.extraction.gemini_extractor import GeminiExtractError
from lease_companion_ai.ingestion import pdf_text
from lease_companion_ai.ingestion.pdf_text import extract_document_text
from lease_companion_ai.pipelines import minimum_mvp as pipe
from lease_companion_ai.pipelines.minimum_mvp import extract_documents

# 디지털 판정 임계값(100자/쪽)을 넘기는 본문 채움. 실제 계약서·등기부는 쪽당 수천 자 —
# 한두 줄짜리 픽스처는 실문서가 아니라 스캔본 부스러기로 오판된다. 파서 키워드(소유자·
# 임대인·보증금·근저당 등)가 없는 중립 문장만 쓴다.
_FILLER = "\n" + ("본 문서는 교육 및 실습 목적의 가상 자료로서 어떠한 법적 효력도 발생하지 아니한다.\n" * 10)


@pytest.fixture(autouse=True)
def _regex_parser_only(monkeypatch):
    """Gemini 구조화 차단 → 정규식 파서 경로 고정. API 키가 있어도 테스트가 실호출·과금·비결정성을 만들지 않는다."""
    def _no_api(_text):
        raise GeminiExtractError("test: gemini disabled")

    monkeypatch.setattr(pipe, "extract_contract_fields", _no_api)
    monkeypatch.setattr(pipe, "extract_registry_fields", _no_api)


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
        + _FILLER
    )

    extraction = extract_documents(contract, "contract.pdf", registry, "registry.pdf")

    assert extraction["contract"]["fields"]["landlord_name"] == "이정훈"
    assert extraction["registry"]["fields"]["owner_names"] == ["이정훈"]
    assert extraction["registry"]["fields"]["mortgage_present"] is True
    assert extraction["contract"]["read_method"] == "digital"  # 텍스트 레이어 PDF → OCR 아님
    assert extraction["registry"]["read_method"] == "digital"
    assert extraction["contract"]["read_ok"] is True
    assert extraction["registry"]["read_ok"] is True


def test_one_document_read_failure_does_not_block_the_other():
    contract = _pdf_bytes("주택임대차계약서\n임대인: 이정훈 (서명)" + _FILLER)

    extraction = extract_documents(contract, "contract.pdf", b"%not a valid pdf%", "registry.pdf")

    assert extraction["contract"]["read_ok"] is True  # 정상 문서는 그대로 추출
    assert extraction["registry"]["read_ok"] is False  # 깨진 문서만 실패 격리
    assert extraction["registry"]["error"]  # 사용자에게 전달할 사유 존재


def test_scanned_pdf_with_only_stray_text_falls_back_to_ocr(monkeypatch):
    """스캔본은 워터마크·페이지번호 한 줄만 텍스트 레이어에 갖는 경우가 흔하다.

    글자 유무만 보면 이 껍데기를 디지털로 오판해 OCR을 건너뛰고 빈 추출을 반환한다.
    """
    monkeypatch.setattr(pdf_text, "_ocr_text", lambda content, filename: "OCR이 읽은 본문")
    stray = _pdf_bytes("열람용 워터마크 · 1 / 3")  # 부스러기 수십 자

    text, method = extract_document_text(stray, "scan.pdf")

    assert method == "ocr"
    assert text == "OCR이 읽은 본문"


def test_digital_pdf_above_threshold_never_calls_ocr(monkeypatch):
    """디지털 PDF는 로컬 처리 유지 — OCR로 새면 비용·정확도 손해에 PII까지 외부로 나간다."""
    def _fail(content, filename):
        raise AssertionError("디지털 PDF에 OCR이 호출되면 안 된다")

    monkeypatch.setattr(pdf_text, "_ocr_text", _fail)
    digital = _pdf_bytes("주택임대차계약서\n" + "보증금 반환 조건 조항 본문. " * 20)

    text, method = extract_document_text(digital, "contract.pdf")

    assert method == "digital"
    assert "주택임대차계약서" in text


def test_force_ocr_overrides_digital_pdf(monkeypatch):
    """데모·충실도 비교용 강제 OCR: 텍스트 레이어가 멀쩡해도 OCR로 읽는다."""
    monkeypatch.setattr(pdf_text, "_ocr_text", lambda content, filename: "강제 OCR 결과")
    digital = _pdf_bytes("주택임대차계약서\n" + "보증금 반환 조건 조항 본문. " * 20)

    text, method = extract_document_text(digital, "contract.pdf", force_ocr=True)

    assert method == "ocr"
    assert text == "강제 OCR 결과"


def test_force_ocr_on_broken_pdf_still_reports_read_error(monkeypatch):
    """강제 OCR이 깨진 PDF를 ocr.py로 넘기면 fitz.open이 raw 예외로 터져 500이 된다."""
    monkeypatch.setattr(pdf_text, "_ocr_text", lambda content, filename: "여기 오면 안 된다")

    extraction = extract_documents(
        _pdf_bytes("주택임대차계약서\n임대인: 이정훈 (서명)"), "contract.pdf",
        b"%not a valid pdf%", "registry.pdf", force_ocr=True,
    )

    assert extraction["registry"]["read_ok"] is False
    assert extraction["registry"]["error"]


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
        + _FILLER
    )
    registry = _pdf_bytes(
        "등기사항전부증명서\n"
        "소재지: 서울특별시 가온구 나래로 12, 305동 1201호\n"
        "소유자: 홍길동"
        + _FILLER
    )

    extraction = extract_documents(contract, "contract.pdf", registry, "registry.pdf")
    fields = extraction["contract"]["fields"]

    assert fields["landlord_name"] == "홍길동"
    assert fields["property_address"] == "서울특별시 가온구 나래로 12, 305동 1201호"
