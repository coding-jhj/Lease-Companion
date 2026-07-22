"""버전 관리된 특약 카탈로그(data/rules/special_clause_catalog.json) 로더."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from lease_companion_ai.special_clauses.models import SpecialClauseCatalogEntry

_CATALOG_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "rules" / "special_clause_catalog.json"
)


@lru_cache(maxsize=1)
def load_special_clause_catalog() -> tuple[SpecialClauseCatalogEntry, ...]:
    data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    entries: list[SpecialClauseCatalogEntry] = []
    for entry in data["entries"]:
        entries.append(
            SpecialClauseCatalogEntry(
                catalog_id=entry["catalog_id"],
                version=entry["version"],
                display_name=entry["display_name"],
                related_rule_ids=tuple(entry["related_rule_ids"]),
                related_judgment_ids=tuple(entry["related_judgment_ids"]),
                include_patterns=tuple(re.compile(p) for p in entry["include_patterns"]),
                exclude_patterns=tuple(re.compile(p) for p in entry["exclude_patterns"]),
                allowed_source_sections=tuple(dict(s) for s in entry["allowed_source_sections"]),
                prohibited_terms=tuple(entry["explanation_boundary"]["prohibited_terms"]),
            )
        )
    return tuple(entries)
