from __future__ import annotations

from lease_companion_ai.rag.indexing.chunker import chunk_sections
from lease_companion_ai.rag.models import RetrievalQuery
from lease_companion_ai.rag.retrieval.bm25 import BM25Index, tokenize


def _chunks(source_metadata):
    return chunk_sections(
        source_metadata,
        [
            ("가", "근저당권 선순위 권리 채권최고액 확인"),
            ("나", "임대인 소유자 계약 상대 이름 확인"),
            ("다", "계약 직전 최신 등기사항증명서 발급일 확인"),
        ],
    )


def test_tokenizer_is_deterministic_and_case_insensitive():
    assert tokenize("R03 근저당권, CHECK") == ["r03", "근저당권", "check"]


def test_bm25_returns_deterministic_relevant_ranking(source_metadata):
    index = BM25Index(_chunks(source_metadata))
    query = RetrievalQuery(
        rule_id="R03",
        rule_name="근저당권 존재 탐지",
        status="확인 필요",
        deidentified_clause_context="선순위 권리 채권최고액",
    )

    first = index.search(query)
    second = index.search(query)

    assert first == second
    assert first[0].chunk.section == "가"
    assert [hit.rank for hit in first] == list(range(1, len(first) + 1))
    assert all(hit.retrieval_method == "bm25" for hit in first)


def test_bm25_tie_breaks_by_chunk_id(source_metadata):
    chunks = chunk_sections(source_metadata, [("가", "공통어"), ("나", "공통어")])
    results = BM25Index(list(reversed(chunks))).search("공통어")
    assert [hit.chunk.chunk_id for hit in results] == sorted(chunk.chunk_id for chunk in chunks)


def test_bm25_returns_empty_for_no_overlap(source_metadata):
    assert BM25Index(_chunks(source_metadata)).search("완전히다른질의") == []
