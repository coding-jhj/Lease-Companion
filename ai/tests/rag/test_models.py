from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from lease_companion_ai.rag.indexing.chunker import chunk_sections
from lease_companion_ai.rag.models import RagSourceMetadata, RetrievalHit, RetrievalQuery


def test_metadata_rejects_non_official_or_insecure_source(source_metadata):
    payload = source_metadata.model_dump()
    payload["source_status"] = "unverified"
    with pytest.raises(ValidationError):
        RagSourceMetadata.model_validate(payload)

    payload = source_metadata.model_dump()
    payload["source_url"] = "http://example.go.kr/source"
    with pytest.raises(ValidationError):
        RagSourceMetadata.model_validate(payload)


def test_retrieval_query_contains_only_explicit_deidentified_context():
    query = RetrievalQuery(
        rule_id="R03",
        rule_name="근저당권 존재 탐지",
        status="확인 필요",
        deidentified_clause_context="[ADDRESS_1] 선순위 권리 확인",
    )
    assert query.to_search_text() == "R03 근저당권 존재 탐지 확인 필요 [ADDRESS_1] 선순위 권리 확인"


def test_retrieval_hit_rejects_non_finite_score(source_metadata):
    chunk = chunk_sections(source_metadata, [("항목", "공식 확인 항목")])[0]
    with pytest.raises(ValidationError):
        RetrievalHit(
            chunk=chunk,
            score=math.inf,
            rank=1,
            retrieval_method="bm25",
        )
