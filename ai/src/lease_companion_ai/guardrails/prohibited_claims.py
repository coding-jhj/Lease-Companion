"""서비스가 제공하면 안 되는 단정적 결론을 탐지한다."""

from __future__ import annotations

import re


_PROHIBITED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:계약|주택|거래).{0,12}(?:안전|위험)(?:합니다|해요|하다|한\s*계약)"),
    re.compile(r"(?:안전|위험)한\s*(?:계약|주택|거래)(?:입니다|이에요)?"),
    re.compile(
        r"(?:전세\s*사기|사기).{0,12}"
        r"(?:입니다|아닙니다|확실|가능성(?:이)?\s*(?:없|높|낮)|가능성\s*점수)"
    ),
    re.compile(r"(?:합법|위법|불법|적법)(?:입니다|이\s*아닙니다|으로\s*확정)"),
    re.compile(r"계약(?:해도|하셔도)\s*(?:됩니다|괜찮습니다)"),
    re.compile(r"계약(?:하지\s*마십시오|을\s*피하십시오|을\s*체결하십시오)"),
)


def has_prohibited_claim(texts: tuple[str, ...]) -> bool:
    return any(pattern.search(text) for text in texts for pattern in _PROHIBITED_PATTERNS)
