"""특약 카탈로그·매칭 후보의 결정론적 데이터 타입.

매칭은 판정 입력 준비만 담당한다 — status/urgency/reason을 만들지 않는다.
canonical 저장 타입은 schemas.unified.SpecialClauseReview이며, 여기 후보는 그 입력을 만든다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SpecialClauseCatalogEntry:
    catalog_id: str
    version: str
    display_name: str
    related_rule_ids: tuple[str, ...]
    related_judgment_ids: tuple[str, ...]
    include_patterns: tuple[re.Pattern[str], ...]
    exclude_patterns: tuple[re.Pattern[str], ...]
    allowed_source_sections: tuple[dict[str, str], ...]
    prohibited_terms: tuple[str, ...]


@dataclass(frozen=True)
class SpecialClauseCandidate:
    """확인 특약 1개의 후보 매칭 결과. 후보 R/J와 검색 범위만 담고 판정을 만들지 않는다."""

    clause_id: str
    original_text: str
    catalog_ids: tuple[str, ...]
    match_method: str  # "catalog_exact" | "catalog_pattern" | "unmatched"
    related_rule_ids: tuple[str, ...]
    related_judgment_ids: tuple[str, ...]
    allowed_source_sections: tuple[dict[str, str], ...]
