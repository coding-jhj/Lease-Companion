"""공식자료 section 경계를 보존하는 결정적 문자 기반 청킹."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from lease_companion_ai.rag.models import RagChunk, RagSourceMetadata


def normalize_source_text(text: str) -> str:
    """줄바꿈과 줄 내부 공백을 정규화하되 section 문단 경계는 보존한다."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def build_chunk_id(
    metadata: RagSourceMetadata,
    *,
    section: str,
    ordinal: int,
    text: str,
) -> str:
    payload = "\x1f".join(
        (metadata.source_id, metadata.source_sha256, section, str(ordinal), text)
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{metadata.source_id}:{digest}"


def _split_text(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars는 양수여야 합니다.")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars는 0 이상 max_chars 미만이어야 합니다.")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        limit = min(start + max_chars, len(text))
        end = limit
        if limit < len(text):
            minimum = start + max_chars // 2
            newline = text.rfind("\n", minimum, limit + 1)
            space = text.rfind(" ", minimum, limit + 1)
            boundary = max(newline, space)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        next_start = end - overlap_chars
        start = next_start if next_start > start else end
    return chunks


def chunk_sections(
    metadata: RagSourceMetadata,
    sections: Sequence[tuple[str, str]],
    *,
    max_chars: int = 1200,
    overlap_chars: int = 120,
) -> list[RagChunk]:
    """section별 텍스트를 입력 순서대로 청킹하고 전역 ordinal을 부여한다."""
    chunks: list[RagChunk] = []
    seen_ids: set[str] = set()
    ordinal = 0
    for raw_section, raw_text in sections:
        section = normalize_source_text(raw_section)
        text = normalize_source_text(raw_text)
        if not section or not text:
            continue
        for part in _split_text(text, max_chars=max_chars, overlap_chars=overlap_chars):
            chunk_id = build_chunk_id(
                metadata,
                section=section,
                ordinal=ordinal,
                text=part,
            )
            if chunk_id in seen_ids:
                raise ValueError(f"중복 chunk_id가 생성되었습니다: {chunk_id}")
            seen_ids.add(chunk_id)
            chunks.append(
                RagChunk(
                    chunk_id=chunk_id,
                    metadata=metadata,
                    section=section,
                    ordinal=ordinal,
                    text=part,
                )
            )
            ordinal += 1
    if not chunks:
        raise ValueError("청킹할 유효한 section 텍스트가 없습니다.")
    return chunks
