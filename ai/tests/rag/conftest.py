from __future__ import annotations

import hashlib
from datetime import date

import pytest

from lease_companion_ai.rag.models import RagSourceMetadata


@pytest.fixture
def source_metadata() -> RagSourceMetadata:
    return RagSourceMetadata(
        source_id="SRC-TEST-OFFICIAL",
        document_title="합성 공식자료 테스트 fixture",
        institution="테스트 공공기관",
        document_type="공식 가이드",
        article_or_section="전체",
        effective_date=None,
        source_url="https://example.go.kr/official",
        collected_date=date(2026, 7, 16),
        source_sha256=hashlib.sha256("합성 fixture".encode()).hexdigest(),
        usage_terms="합성 테스트 전용",
    )
