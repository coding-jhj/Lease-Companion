"""결정론적 비교를 위한 최소 정규화 함수."""

from __future__ import annotations

import re


def normalize_name(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^0-9A-Za-z가-힣]", "", value).casefold()
    return normalized or None


def normalize_address(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^0-9A-Za-z가-힣]", "", value).casefold()
    return normalized or None
