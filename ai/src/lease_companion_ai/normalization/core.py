"""결정론적 비교를 위한 최소 정규화 함수."""

from __future__ import annotations

import re


def _strip(value: str | None) -> str | None:
    """비교용 정규화: 문자·숫자 외 제거 후 casefold.

    ponytail: 주소는 번지·동/호 표기 차이(예: '12' vs '12번지', '로' vs '길')에 취약하다.
    실주소 비교가 필요해지면 동/호 파싱을 추가한다. 현재는 합성 정형 데이터 기준.
    """
    if not value:
        return None
    normalized = re.sub(r"[^0-9A-Za-z가-힣]", "", value).casefold()
    return normalized or None


def normalize_name(value: str | None) -> str | None:
    return _strip(value)


def normalize_address(value: str | None) -> str | None:
    return _strip(value)
