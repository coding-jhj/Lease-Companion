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
