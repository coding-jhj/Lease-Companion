"""확인 특약 문장을 카탈로그 유형 후보로 결정론적으로 매칭한다.

입력은 사용자 확인 완료 값을 그대로 사용하고, 공백만 정규화하며 새 법적 의미를 만들지 않는다.
카탈로그는 후보 R/J와 검색 범위를 고르지만 status/urgency/reason을 반환하지 않는다.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from lease_companion_ai.special_clauses.catalog import load_special_clause_catalog
from lease_companion_ai.special_clauses.models import SpecialClauseCandidate

_WHITESPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """매칭용 정규화 — 공백/탭만 단일 공백으로. 원문 의미는 바꾸지 않는다."""
    return _WHITESPACE.sub(" ", text).strip()


def _dedup(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def match_special_clauses(
    clauses: Sequence[str], *, start_ordinal: int = 1
) -> tuple[SpecialClauseCandidate, ...]:
    """확인 특약 원문 목록 → 후보 목록. 한 문장에 여러 논점이면 여러 catalog_id를 허용한다."""
    catalog = load_special_clause_catalog()
    candidates: list[SpecialClauseCandidate] = []
    for offset, raw in enumerate(clauses):
        normalized = _normalize(raw)
        matched = [
            entry
            for entry in catalog
            if any(pattern.search(normalized) for pattern in entry.include_patterns)
            and not any(pattern.search(normalized) for pattern in entry.exclude_patterns)
        ]
        clause_id = f"SC-{start_ordinal + offset:04d}"
        if matched:
            sections: dict[tuple[str, str], dict[str, str]] = {}
            for entry in matched:
                for section in entry.allowed_source_sections:
                    sections[(section["source_id"], section["article_or_section"])] = section
            candidates.append(
                SpecialClauseCandidate(
                    clause_id=clause_id,
                    original_text=raw,
                    catalog_ids=_dedup(tuple(entry.catalog_id for entry in matched)),
                    match_method="catalog_pattern",
                    related_rule_ids=_dedup(
                        tuple(rid for entry in matched for rid in entry.related_rule_ids)
                    ),
                    related_judgment_ids=_dedup(
                        tuple(jid for entry in matched for jid in entry.related_judgment_ids)
                    ),
                    allowed_source_sections=tuple(sections.values()),
                )
            )
        else:
            candidates.append(
                SpecialClauseCandidate(
                    clause_id=clause_id,
                    original_text=raw,
                    catalog_ids=(),
                    match_method="unmatched",
                    related_rule_ids=(),
                    related_judgment_ids=(),
                    allowed_source_sections=(),
                )
            )
    return tuple(candidates)
