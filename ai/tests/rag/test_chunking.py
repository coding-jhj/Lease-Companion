from __future__ import annotations

import pytest

from lease_companion_ai.rag.indexing.chunker import chunk_sections, normalize_source_text


def test_normalize_source_text_is_stable():
    assert normalize_source_text("  첫째  줄\r\n\r\n둘째\t줄  ") == "첫째 줄\n둘째 줄"


def test_chunk_ids_and_order_are_deterministic(source_metadata):
    sections = [
        ("제1항", "계약 상대와 등기상 소유자를 확인합니다." * 4),
        ("제2항", "계약 직전 최신 등기사항증명서를 확인합니다." * 4),
    ]
    first = chunk_sections(source_metadata, sections, max_chars=50, overlap_chars=10)
    second = chunk_sections(source_metadata, sections, max_chars=50, overlap_chars=10)

    assert first == second
    assert [chunk.ordinal for chunk in first] == list(range(len(first)))
    assert len({chunk.chunk_id for chunk in first}) == len(first)
    assert all(len(chunk.text) <= 50 for chunk in first)
    assert {chunk.section for chunk in first} == {"제1항", "제2항"}


@pytest.mark.parametrize(
    ("max_chars", "overlap_chars"),
    [(0, 0), (10, -1), (10, 10)],
)
def test_chunking_rejects_invalid_window(source_metadata, max_chars, overlap_chars):
    with pytest.raises(ValueError):
        chunk_sections(
            source_metadata,
            [("항목", "테스트 텍스트")],
            max_chars=max_chars,
            overlap_chars=overlap_chars,
        )


def test_chunking_rejects_empty_sections(source_metadata):
    with pytest.raises(ValueError, match="유효한 section"):
        chunk_sections(source_metadata, [("", ""), ("항목", "  ")])


def test_chunking_does_not_cut_articles_or_special_clause_sentences(source_metadata):
    special_clause = (
        "· 주택을 인도받은 임차인은 약정일까지 주민등록(전입신고)과 "
        "주택임대차계약서상 확정일자를 받기로 하고, 임대인은 위 약정일자의 "
        "다음날까지 임차주택에 저당권 등 담보권을 설정할 수 없다."
    )
    text = "\n".join(
        [
            "제10조(비용의 정산) 임차인은 장기수선충당금을 임대인에게 반환 청구할 수 있다.",
            "[특약사항]",
            special_clause,
            "· 임대인이 위 특약을 위반한 경우 임차인은 계약을 해제 또는 해지할 수 있다.",
        ]
    )

    chunks = chunk_sections(
        source_metadata,
        [("전체", text)],
        max_chars=180,
        overlap_chars=30,
    )

    assert any(special_clause in chunk.text for chunk in chunks)
    assert all(
        line.startswith(("제10조", "[특약사항]", "·"))
        for chunk in chunks
        for line in chunk.text.splitlines()
    )
    for chunk in chunks:
        lines = chunk.text.splitlines()
        assert all(
            index < len(lines) - 1
            for index, line in enumerate(lines)
            if line.startswith("[") and line.endswith("]")
        )


def test_section_heading_stays_with_its_first_body_paragraph(source_metadata):
    text = "\n".join(
        [
            "제13조(교부) 임대인은 관련 서류를 임차인에게 교부한다.",
            "[특약사항]",
            "· 임차인은 약정일까지 전입신고와 확정일자를 받는다.",
            "· 임대인은 다음날까지 담보권을 설정하지 않는다.",
            "[수선비용 부담의 해석 기준]",
            "· 임대인 부담: 주요 설비의 노후로 인한 수선비용.",
        ]
    )

    chunks = chunk_sections(
        source_metadata,
        [("전체", text)],
        max_chars=105,
        overlap_chars=20,
    )

    assert all(
        not chunk.text.endswith(("[특약사항]", "[수선비용 부담의 해석 기준]"))
        for chunk in chunks
    )
    assert any(
        "[수선비용 부담의 해석 기준]\n· 임대인 부담:" in chunk.text
        for chunk in chunks
    )
