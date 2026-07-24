from pathlib import Path

import fitz


FIXTURE_TEXT = """합성·비식별 주택임대차계약서
소재지: 서울특별시 가온구 나래로 12, 305동 1201호
보증금: 금 삼억원 (300,000,000원)
임대차 기간: 2026년 8월 1일부터 2028년 7월 31일까지
특약사항
보증금 반환은 신규 임차인의 입주 및 보증금 지급 완료 후 진행한다.
임대인: 이정훈 (합성 인물)
임차인: 강해린 (합성 인물)
본 문서는 자동화 검증을 위한 비식별 합성 자료이며 법적 효력이 없다.
"""


def main() -> None:
    output = Path(__file__).with_name("synthetic-non-identifying-lease.pdf")
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    remaining = page.insert_textbox(
        fitz.Rect(40, 40, 555, 802),
        FIXTURE_TEXT,
        fontsize=10,
        fontname="korea",
    )
    if remaining < 0:
        raise RuntimeError("합성 계약서 텍스트가 PDF 한 페이지를 초과했습니다.")
    document.save(output, garbage=4, deflate=True)
    document.close()


if __name__ == "__main__":
    main()
