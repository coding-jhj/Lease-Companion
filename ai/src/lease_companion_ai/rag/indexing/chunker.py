"""공식자료의 section·문단 경계를 보존하는 결정적 청킹."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from lease_companion_ai.rag.models import RagChunk, RagSourceMetadata


_ARTICLE_HEADING = re.compile(r"^(제\d+조(?:의\d+)?)(?:\([^)]*\))?")
_BRACKET_HEADING = re.compile(r"^(\[[^\]]+\]|【[^】]+】)")
_CIRCLED_PARAGRAPHS = {"제1항": "①", "제2항": "②", "제3항": "③", "제4항": "④"}


def normalize_source_text(text: str) -> str:
    """줄바꿈과 줄 내부 공백을 정규화하되 section 문단 경계는 보존한다."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _article_blocks(text: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in normalize_source_text(text).splitlines():
        match = _ARTICLE_HEADING.match(line)
        if match:
            current = match.group(1)
            blocks[current] = [line]
        elif current is not None and _BRACKET_HEADING.match(line) is None:
            blocks[current].append(line)
        elif _BRACKET_HEADING.match(line):
            current = None
    return blocks


def _bracket_block(text: str, heading: str) -> list[str]:
    lines = normalize_source_text(text).splitlines()
    collected: list[str] = []
    active = False
    for line in lines:
        match = _BRACKET_HEADING.match(line)
        if match:
            if active:
                break
            active = match.group(1) == heading
        if active:
            collected.append(line)
    return collected


def extract_named_section(text: str, article_or_section: str) -> str:
    """카탈로그의 조·항 이름으로 공식 원문 범위를 결정적으로 추출한다."""

    normalized = normalize_source_text(text)
    article_ids = tuple(dict.fromkeys(re.findall(r"제\d+조(?:의\d+)?", article_or_section)))
    if article_ids:
        blocks = _article_blocks(normalized)
        selected: list[str] = []
        for article_id in article_ids:
            selected.extend(blocks.get(article_id, ()))
        paragraph_match = re.search(r"제([1-4])항(?:~제([1-4])항)?", article_or_section)
        if paragraph_match and selected:
            start = int(paragraph_match.group(1))
            end = int(paragraph_match.group(2) or paragraph_match.group(1))
            markers = {_CIRCLED_PARAGRAPHS[f"제{number}항"] for number in range(start, end + 1)}
            selected = [selected[0], *(line for line in selected[1:] if line[:1] in markers)]
        result = normalize_source_text("\n".join(selected))
        if result:
            return result

    bracket = re.match(r"(\[[^\]]+\]|【[^】]+】)", article_or_section)
    if bracket:
        selected = _bracket_block(normalized, bracket.group(1))
        suffix = article_or_section[bracket.end() :].strip()
        if suffix and selected:
            keywords = [token for token in re.findall(r"[0-9A-Za-z가-힣]+", suffix) if len(token) >= 2]
            matching = [line for line in selected[1:] if any(keyword in line for keyword in keywords)]
            selected = [selected[0], *matching] if matching else selected
        result = normalize_source_text("\n".join(selected))
        if result:
            return result

    phrase_aliases = {
        "잔금 지급 전 권리관계 재확인": "권리관계 재확인",
        "담보권 설정 특약 이행 여부 확인": "특약 이행 여부 확인(담보권 설정",
    }
    needle = phrase_aliases.get(article_or_section, article_or_section)
    matching_lines = [line for line in normalized.splitlines() if needle in line]
    if matching_lines:
        return normalize_source_text("\n".join(matching_lines))
    raise ValueError(f"공식 원문에서 section을 찾을 수 없습니다: {article_or_section}")


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

    def split_long_paragraph(paragraph: str) -> list[str]:
        """긴 단일 문단도 우선 문장, 불가피할 때만 단어 경계에서 나눈다."""
        parts: list[str] = []
        remaining = paragraph
        while len(remaining) > max_chars:
            window = remaining[: max_chars + 1]
            sentence_ends = [match.end() for match in re.finditer(r"[.!?]", window)]
            usable_sentence_ends = [
                end for end in sentence_ends if end >= max_chars // 2
            ]
            if usable_sentence_ends:
                end = usable_sentence_ends[-1]
            else:
                end = window.rfind(" ", max_chars // 2, max_chars + 1)
                if end <= 0:
                    end = max_chars
            parts.append(remaining[:end].strip())
            remaining = remaining[end:].strip()
        if remaining:
            parts.append(remaining)
        return parts

    # 줄 하나가 조항·특약 항목 하나인 정규화 원문의 구조를 보존한다.
    paragraphs = [
        part
        for line in text.split("\n")
        for part in split_long_paragraph(line)
        if part
    ]
    units: list[str] = []
    index = 0
    while index < len(paragraphs):
        paragraph = paragraphs[index]
        is_section_heading = (
            re.fullmatch(r"\[[^\]]+\](?:\s+.+)?", paragraph) is not None
            or re.fullmatch(r"【[^】]+】", paragraph) is not None
        )
        if is_section_heading and index + 1 < len(paragraphs):
            units.append(f"{paragraph}\n{paragraphs[index + 1]}")
            index += 2
            continue
        units.append(paragraph)
        index += 1

    chunks: list[str] = []
    current: list[str] = []

    for paragraph in units:
        candidate = "\n".join([*current, paragraph])
        if current and len(candidate) > max_chars:
            chunks.append("\n".join(current))

            overlap: list[str] = []
            overlap_length = 0
            for previous in reversed(current):
                added_length = len(previous) + (1 if overlap else 0)
                if overlap_length + added_length > overlap_chars:
                    break
                overlap.insert(0, previous)
                overlap_length += added_length
            current = overlap
            candidate = "\n".join([*current, paragraph])
            if len(candidate) > max_chars:
                current = []

        current.append(paragraph)

    if current:
        chunks.append("\n".join(current))
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
