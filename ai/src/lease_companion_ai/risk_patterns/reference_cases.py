"""검증된 공개 참고 사례 corpus의 결정적 로컬 검색."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lease_companion_ai.schemas.unified import ReferenceCase


_PATTERN_ID = re.compile(r"^DP\d{2}$")


@dataclass(frozen=True)
class ReferenceCaseEntry:
    pattern_ids: tuple[str, ...]
    tags: tuple[str, ...]
    reference_case: ReferenceCase


def _catalog_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "data"
        / "reference-cases"
        / "verified_reference_cases.json"
    )


@lru_cache(maxsize=1)
def load_verified_reference_cases() -> tuple[ReferenceCaseEntry, ...]:
    payload = json.loads(_catalog_path().read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0.0":
        raise ValueError("유사 참고 사례 corpus schema_version이 1.0.0이 아닙니다.")

    entries: list[ReferenceCaseEntry] = []
    seen_ids: set[str] = set()
    for raw in payload.get("cases", []):
        pattern_ids = tuple(raw["pattern_ids"])
        if not pattern_ids or any(not _PATTERN_ID.fullmatch(item) for item in pattern_ids):
            raise ValueError("유사 참고 사례 pattern_ids가 올바르지 않습니다.")
        reference_case = ReferenceCase.model_validate(raw["reference_case"])
        if reference_case.reference_case_id in seen_ids:
            raise ValueError("유사 참고 사례 ID가 중복되었습니다.")
        seen_ids.add(reference_case.reference_case_id)
        entries.append(
            ReferenceCaseEntry(
                pattern_ids=pattern_ids,
                tags=tuple(raw.get("tags", [])),
                reference_case=reference_case,
            )
        )
    return tuple(entries)


def search_reference_cases(
    pattern_id: str, *, limit: int = 2
) -> tuple[ReferenceCase, ...]:
    """Return verified cases mapped to a DP display pattern.

    Search is local and deterministic.  Results never participate in R/J status,
    urgency, evidence selection, or action generation.
    """

    if not _PATTERN_ID.fullmatch(pattern_id):
        raise ValueError("pattern_id는 DP 두 자리 형식이어야 합니다.")
    if limit < 1:
        return ()
    return tuple(
        entry.reference_case
        for entry in load_verified_reference_cases()
        if pattern_id in entry.pattern_ids
    )[:limit]
