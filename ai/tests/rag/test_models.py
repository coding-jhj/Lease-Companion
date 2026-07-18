from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from lease_companion_ai.rag.indexing.chunker import chunk_sections
from lease_companion_ai.rag.models import (
    JudgmentRetrievalQuery,
    RagSourceMetadata,
    RetrievalHit,
    RetrievalQuery,
)


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


def test_judgment_retrieval_query_fixes_j_id_and_source_allowlist():
    query = JudgmentRetrievalQuery(
        judgment_id="J01",
        judgment_name="계약서 임대인=등기 소유자",
        status="불일치",
        allowed_source_ids=("SRC-STD-LEASE", "SRC-REGISTRY-SAMPLE"),
        deidentified_clause_context="[PERSON_1]과 등기 소유자 불일치",
    )

    assert query.to_search_text() == (
        "J01 계약서 임대인=등기 소유자 불일치 "
        "[PERSON_1]과 등기 소유자 불일치"
    )
    with pytest.raises(ValidationError):
        JudgmentRetrievalQuery(
            judgment_id="R01",
            judgment_name="잘못된 축",
            status="확인 필요",
            allowed_source_ids=("SRC-STD-LEASE",),
        )
    with pytest.raises(ValidationError):
        JudgmentRetrievalQuery(
            judgment_id="J01",
            judgment_name="중복 출처",
            status="확인 필요",
            allowed_source_ids=("SRC-STD-LEASE", "SRC-STD-LEASE"),
        )


def test_retrieval_hit_rejects_non_finite_score(source_metadata):
    chunk = chunk_sections(source_metadata, [("항목", "공식 확인 항목")])[0]
    with pytest.raises(ValidationError):
        RetrievalHit(
            chunk=chunk,
            score=math.inf,
            rank=1,
            retrieval_method="bm25",
        )
