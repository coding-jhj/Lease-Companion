"""HUG 공식 보도자료 목록에서 최근 전세사기 자료를 조회한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen


HUG_PRESS_RELEASE_LIST_URL = (
    "https://www.khug.or.kr/khmb/m/hs/nd/hsnd000001.jsp"
)
HUG_PRESS_RELEASE_DETAIL_BASE_URL = (
    "https://www.khug.or.kr/khmb/m/hs/nd/"
)
MOLIT_PRESS_RELEASE_LIST_URL = (
    "https://www.korea.kr/briefing/pressReleaseList.do"
)
MOLIT_PRESS_RELEASE_DETAIL_BASE_URL = (
    "https://www.korea.kr/briefing/pressReleaseView.do"
)
_DETAIL_PATH = re.compile(r"^hsnd000002\.jsp\?idx=\d+$")
_MOLIT_DETAIL_PATH = re.compile(
    r"^/briefing/pressReleaseView\.do\?newsId=(\d+).*$"
)
_PUBLISHED_AT = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
_ISO_PUBLISHED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class PublicPressReleaseSourceError(RuntimeError):
    """공식 보도자료 원본을 읽거나 해석하지 못한 경우."""


@dataclass(frozen=True)
class PublicPressRelease:
    title: str
    publisher: str
    published_at: str
    source_url: str


@dataclass(frozen=True)
class PatternSearchRule:
    query: str
    title_terms: tuple[str, ...]


PATTERN_SEARCH_RULES: dict[str, PatternSearchRule] = {
    "DP01": PatternSearchRule(
        query="가짜 임대인",
        title_terms=("가짜 임대인", "임대인 사칭", "소유자 사칭", "명의 도용", "대리인"),
    ),
    "DP02": PatternSearchRule(
        query="전세사기 계좌",
        title_terms=("계좌", "명의", "입금", "제3자"),
    ),
    "DP03": PatternSearchRule(
        query="깡통전세",
        title_terms=("깡통전세", "전세가율", "주택가격", "주택가치", "시세"),
    ),
    "DP04": PatternSearchRule(
        query="전세 근저당",
        title_terms=("근저당", "선순위", "담보", "권리관계"),
    ),
    "DP05": PatternSearchRule(
        query="신탁주택 전세",
        title_terms=("신탁", "신탁주택", "신탁회사"),
    ),
    "DP06": PatternSearchRule(
        query="선순위 임차보증금",
        title_terms=("선순위 임차", "임차보증금", "다가구", "확정일자"),
    ),
    "DP07": PatternSearchRule(
        query="전세 권리변동",
        title_terms=("권리변동", "임대인 변경", "담보대출", "계약 당일"),
    ),
    "DP08": PatternSearchRule(
        query="보증금 미반환",
        title_terms=("보증금 미반환", "보증금 반환", "반환보증", "전세보증금"),
    ),
}


def _pattern_rule(pattern_id: str) -> PatternSearchRule:
    try:
        return PATTERN_SEARCH_RULES[pattern_id]
    except KeyError as exc:
        raise ValueError("pattern_id는 DP01부터 DP08까지만 허용됩니다.") from exc


class _HugPressReleaseParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[PublicPressRelease] = []
        self._detail_path: str | None = None
        self._inside_detail_anchor = False
        self._anchor_text: list[str] = []
        self._pending_title: str | None = None
        self._cell_text: list[str] | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attr_map = dict(attrs)
        if tag == "a":
            href = attr_map.get("href")
            if href and _DETAIL_PATH.fullmatch(href):
                self._detail_path = href
                self._inside_detail_anchor = True
                self._anchor_text = []
        if tag == "td":
            self._cell_text = []

    def handle_data(self, data: str) -> None:
        if self._inside_detail_anchor:
            self._anchor_text.append(data)
        if self._cell_text is not None:
            self._cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._inside_detail_anchor:
            title = " ".join("".join(self._anchor_text).split())
            if title:
                self._pending_title = title
            self._inside_detail_anchor = False
            self._anchor_text = []
            return

        if tag != "td" or self._cell_text is None:
            return
        cell_text = " ".join("".join(self._cell_text).split())
        self._cell_text = None
        if (
            self._detail_path is None
            or self._pending_title is None
            or not _PUBLISHED_AT.fullmatch(cell_text)
        ):
            return
        self.items.append(
            PublicPressRelease(
                title=self._pending_title,
                publisher="주택도시보증공사(HUG)",
                published_at=cell_text.replace(".", "-"),
                source_url=HUG_PRESS_RELEASE_DETAIL_BASE_URL + self._detail_path,
            )
        )
        self._detail_path = None
        self._pending_title = None


def parse_hug_press_releases(html: str) -> tuple[PublicPressRelease, ...]:
    parser = _HugPressReleaseParser()
    parser.feed(html)
    deduplicated: dict[str, PublicPressRelease] = {}
    for item in parser.items:
        deduplicated.setdefault(item.source_url, item)
    return tuple(deduplicated.values())


class _MolitPressReleaseParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[PublicPressRelease] = []
        self._news_id: str | None = None
        self._inside_title = False
        self._title_parts: list[str] = []
        self._published_at: str | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            match = _MOLIT_DETAIL_PATH.fullmatch(href or "")
            if match and "repCode=A00006" in (href or ""):
                self._news_id = match.group(1)
                self._title_parts = []
                self._published_at = None
        if tag == "strong" and self._news_id is not None:
            self._inside_title = True

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._title_parts.append(data)
        text = data.strip()
        if self._news_id is not None and _ISO_PUBLISHED_AT.fullmatch(text):
            self._published_at = text

    def handle_endtag(self, tag: str) -> None:
        if tag == "strong":
            self._inside_title = False
            return
        if tag != "a" or self._news_id is None:
            return
        title = " ".join("".join(self._title_parts).split())
        if title and self._published_at:
            query = urlencode(
                {"newsId": self._news_id, "repCode": "A00006"}
            )
            self.items.append(
                PublicPressRelease(
                    title=title,
                    publisher="국토교통부",
                    published_at=self._published_at,
                    source_url=f"{MOLIT_PRESS_RELEASE_DETAIL_BASE_URL}?{query}",
                )
            )
        self._news_id = None
        self._title_parts = []
        self._published_at = None


def parse_molit_press_releases(html: str) -> tuple[PublicPressRelease, ...]:
    parser = _MolitPressReleaseParser()
    parser.feed(html)
    deduplicated: dict[str, PublicPressRelease] = {}
    for item in parser.items:
        deduplicated.setdefault(item.source_url, item)
    return tuple(deduplicated.values())


def _read_official_source(
    request: Request, *, charset: str, source_name: str
) -> str:
    try:
        with urlopen(request, timeout=8) as response:  # noqa: S310 - 고정 허용 URL
            payload = response.read(1_000_001)
            if len(payload) > 1_000_000:
                raise PublicPressReleaseSourceError(
                    f"{source_name} 응답 크기가 허용 범위를 초과했습니다."
                )
            response_charset = response.headers.get_content_charset() or charset
    except PublicPressReleaseSourceError:
        raise
    except Exception as exc:
        raise PublicPressReleaseSourceError(
            f"{source_name} 보도자료를 불러오지 못했습니다."
        ) from exc
    return payload.decode(response_charset, errors="replace")


def fetch_hug_press_releases(
    *, pattern_id: str, limit: int = 2
) -> tuple[PublicPressRelease, ...]:
    """HUG 최신 목록에서 선택한 피해 유형과 관련된 보도자료를 반환한다."""

    safe_limit = min(max(limit, 1), 2)
    rule = _pattern_rule(pattern_id)
    # HUG 검색 폼은 레거시 문자셋 처리에 따라 한글 검색어가 깨질 수 있다.
    # 최신 100건만 요청한 뒤 제목을 로컬에서 결정적으로 필터링한다.
    form_data = urlencode(
        {
            "rowSize": "100",
            "searchCondition": "01",
            "searchKeyword": "",
        }
    ).encode("ascii")
    request = Request(
        HUG_PRESS_RELEASE_LIST_URL,
        data=form_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Lease-Companion/0.1 (+local-mvp)",
        },
        method="POST",
    )
    try:
        parsed = parse_hug_press_releases(
            _read_official_source(
                request,
                charset="euc-kr",
                source_name="HUG",
            )
        )
    except Exception as exc:
        if isinstance(exc, PublicPressReleaseSourceError):
            raise
        raise PublicPressReleaseSourceError(
            "HUG 보도자료 응답을 해석하지 못했습니다."
        ) from exc
    relevant = tuple(
        item
        for item in parsed
        if any(term in item.title for term in rule.title_terms)
    )
    return relevant[:safe_limit]


def fetch_molit_press_releases(
    *, pattern_id: str, limit: int = 2
) -> tuple[PublicPressRelease, ...]:
    """정책브리핑에서 선택한 피해 유형의 국토교통부 보도자료를 반환한다."""

    safe_limit = min(max(limit, 1), 2)
    rule = _pattern_rule(pattern_id)
    today = date.today()
    query = urlencode(
        {
            "repCodeType": "정부부처",
            "repCode": "A00006",
            "startDate": f"{today.year - 3}-01-01",
            "endDate": today.isoformat(),
            "srchWord": rule.query,
        }
    )
    request = Request(
        f"{MOLIT_PRESS_RELEASE_LIST_URL}?{query}",
        headers={"User-Agent": "Lease-Companion/0.1 (+local-mvp)"},
        method="GET",
    )
    try:
        parsed = parse_molit_press_releases(
            _read_official_source(
                request,
                charset="utf-8",
                source_name="국토교통부",
            )
        )
    except Exception as exc:
        if isinstance(exc, PublicPressReleaseSourceError):
            raise
        raise PublicPressReleaseSourceError(
            "국토교통부 보도자료 응답을 해석하지 못했습니다."
        ) from exc
    relevant = tuple(
        item
        for item in parsed
        if any(term in item.title for term in rule.title_terms)
    )
    return relevant[:safe_limit]


def fetch_recent_press_releases(
    *, pattern_id: str, limit: int = 2
) -> tuple[PublicPressRelease, ...]:
    """선택한 피해 유형에 관한 두 공식기관 결과를 최신순으로 반환한다."""

    safe_limit = min(max(limit, 1), 2)
    _pattern_rule(pattern_id)
    collected: list[PublicPressRelease] = []
    failures = 0
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(fetcher, pattern_id=pattern_id, limit=2)
            for fetcher in (fetch_hug_press_releases, fetch_molit_press_releases)
        ]
        for future in as_completed(futures):
            try:
                collected.extend(future.result())
            except PublicPressReleaseSourceError:
                failures += 1
    if failures == 2:
        raise PublicPressReleaseSourceError(
            "모든 공식 보도자료 출처를 불러오지 못했습니다."
        )

    deduplicated: dict[str, PublicPressRelease] = {}
    for item in collected:
        deduplicated.setdefault(item.source_url, item)
    return tuple(
        sorted(
            deduplicated.values(),
            key=lambda item: (item.published_at, item.source_url),
            reverse=True,
        )[:safe_limit]
    )
