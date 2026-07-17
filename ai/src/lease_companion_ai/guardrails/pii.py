"""외부 provider 전송 전에 개인정보를 결정론적으로 토큰화한다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from functools import partial


class PiiKind(str, Enum):
    PERSON = "PERSON"
    ADDRESS = "ADDRESS"
    ACCOUNT = "ACCOUNT"
    RESIDENT_ID = "RESIDENT_ID"
    PHONE = "PHONE"
    EMAIL = "EMAIL"


@dataclass(frozen=True, slots=True)
class PiiReplacement:
    token: str
    original: str
    kind: PiiKind


_LABELED_PATTERNS: tuple[tuple[PiiKind, re.Pattern[str]], ...] = (
    (
        PiiKind.ACCOUNT,
        re.compile(
            r"(?P<prefix>(?:입금\s*)?계좌(?:번호)?\s*[:：]\s*)"
            r"(?P<value>\d{2,6}(?:[- ]\d{2,6}){1,4})"
        ),
    ),
    (
        PiiKind.ADDRESS,
        re.compile(
            r"(?P<prefix>(?:목적물\s*)?(?:주소|소\s*재\s*지)\s*[:：]\s*)"
            r"(?P<value>[^\n,;]{4,100})"
        ),
    ),
    (
        PiiKind.PERSON,
        re.compile(
            r"(?P<prefix>(?:임\s*대\s*인|임\s*차\s*인|소\s*유\s*자|성\s*명|이름|예금주|계좌\s*명의|명의)"
            r"(?:\s*[:：]\s*|\s+))(?P<value>[가-힣]{2,4})"
        ),
    ),
)

_DIRECT_PATTERNS: tuple[tuple[PiiKind, re.Pattern[str]], ...] = (
    (PiiKind.RESIDENT_ID, re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)")),
    (
        PiiKind.EMAIL,
        re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])"),
    ),
    (
        PiiKind.PHONE,
        re.compile(r"(?<!\d)(?:01[016789]|0\d{1,2})[- ]?\d{3,4}[- ]?\d{4}(?!\d)"),
    ),
    (
        PiiKind.ADDRESS,
        re.compile(
            r"(?:[가-힣]{2,}(?:특별시|광역시|특별자치시|도|특별자치도)\s+)?"
            r"[가-힣]{1,}(?:시|군|구)\s+[가-힣A-Za-z0-9·.-]{1,}(?:로|길|동|읍|면)"
            r"(?:\s+\d+(?:-\d+)?)?(?:\s+\d+동\s*\d+호)?"
        ),
    ),
    (
        PiiKind.ACCOUNT,
        re.compile(r"(?<!\d)\d{2,6}(?:-\d{2,6}){2,4}(?!\d)"),
    ),
)
_TOKEN_PATTERN = re.compile(r"\[[A-Z_]+_\d+\]")


class PiiTokenizer:
    """한 provider 요청 안에서 같은 원문을 같은 토큰으로 치환한다."""

    def __init__(self) -> None:
        self._by_original: dict[tuple[PiiKind, str], PiiReplacement] = {}
        self._by_token: dict[str, PiiReplacement] = {}
        self._counts = {kind: 0 for kind in PiiKind}

    @property
    def replacements(self) -> tuple[PiiReplacement, ...]:
        return tuple(self._by_token.values())

    def tokenize(self, text: str | None) -> str | None:
        if text is None:
            return None
        tokenized = text
        for kind, pattern in _LABELED_PATTERNS:
            tokenized = pattern.sub(
                partial(self._replace_labeled, kind),
                tokenized,
            )
        for kind, pattern in _DIRECT_PATTERNS:
            tokenized = pattern.sub(
                partial(self._replace_direct, kind),
                tokenized,
            )
        return tokenized

    def restore(self, text: str | None) -> str | None:
        if text is None:
            return None
        restored = text
        for token, replacement in self._by_token.items():
            restored = restored.replace(token, replacement.original)
        return restored

    def _replace_labeled(self, kind: PiiKind, match: re.Match[str]) -> str:
        value = match.group("value")
        if _TOKEN_PATTERN.fullmatch(value.strip()):
            return match.group(0)
        return match.group("prefix") + self._replacement(kind, value)

    def _replace_direct(self, kind: PiiKind, match: re.Match[str]) -> str:
        return self._replacement(kind, match.group(0))

    def _replacement(self, kind: PiiKind, original: str) -> str:
        key = (kind, original)
        existing = self._by_original.get(key)
        if existing is not None:
            return existing.token
        self._counts[kind] += 1
        token = f"[{kind.value}_{self._counts[kind]}]"
        replacement = PiiReplacement(token=token, original=original, kind=kind)
        self._by_original[key] = replacement
        self._by_token[token] = replacement
        return token


def contains_raw_pii(text: str) -> bool:
    """토큰화 후 외부 요청에 남은 형식형·명시 라벨 개인정보를 찾는다."""

    for _, pattern in _LABELED_PATTERNS:
        for match in pattern.finditer(text):
            if not _TOKEN_PATTERN.fullmatch(match.group("value").strip()):
                return True
    return any(pattern.search(text) for _, pattern in _DIRECT_PATTERNS)
