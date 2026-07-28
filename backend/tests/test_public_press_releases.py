import pytest

from app.services import public_press_releases
from app.services.public_press_releases import (
    PublicPressRelease,
    PublicPressReleaseSourceError,
    fetch_recent_press_releases,
    parse_hug_press_releases,
    parse_molit_press_releases,
)


def test_parse_hug_press_releases_returns_latest_two_source_links():
    html = """
    <table>
      <tr>
        <td><a href="hsnd000002.jsp?idx=37967" class="over-txt">
          HUG, 전세사기 위험 정보 개방한다
        </a></td>
        <td class="txtC">2026.07.15</td>
      </tr>
      <tr>
        <td><a href="hsnd000002.jsp?idx=37757" class="over-txt">
          전세사기 피해지원 및 예방 확대 업무협약
        </a></td>
        <td class="txtC">2026.06.10</td>
      </tr>
    </table>
    """

    items = parse_hug_press_releases(html)

    assert [item.published_at for item in items] == ["2026-07-15", "2026-06-10"]
    assert items[0].publisher == "주택도시보증공사(HUG)"
    assert items[0].source_url == (
        "https://www.khug.or.kr/khmb/m/hs/nd/hsnd000002.jsp?idx=37967"
    )


def test_parse_hug_press_releases_ignores_non_allowlisted_links():
    html = """
    <table><tr>
      <td><a href="https://example.com/fake">가짜 자료</a></td>
      <td class="txtC">2026.07.28</td>
    </tr></table>
    """

    assert parse_hug_press_releases(html) == ()


def test_parse_molit_press_releases_keeps_ministry_title_date_and_source():
    html = """
    <ul><li>
      <a href="/briefing/pressReleaseView.do?newsId=156769934&amp;pageIndex=1&amp;repCodeType=정부부처&amp;repCode=A00006">
        <span class="text">
          <strong>6월 중 <span class="highlight">전세사기</span>피해자등 548건 추가 결정</strong>
          <span class="lead">관련 보도자료 내용입니다.</span>
          <span class="source"><span>2026-07-08</span><span>국토교통부</span></span>
        </span>
      </a>
    </li></ul>
    """

    items = parse_molit_press_releases(html)

    assert len(items) == 1
    assert items[0].title == "6월 중 전세사기피해자등 548건 추가 결정"
    assert items[0].publisher == "국토교통부"
    assert items[0].published_at == "2026-07-08"
    assert items[0].source_url == (
        "https://www.korea.kr/briefing/pressReleaseView.do"
        "?newsId=156769934&repCode=A00006"
    )


def test_combined_results_are_deduplicated_and_sorted(monkeypatch):
    hug_item = PublicPressRelease(
        title="HUG 최신 자료",
        publisher="주택도시보증공사(HUG)",
        published_at="2026-07-15",
        source_url="https://www.khug.or.kr/hug-latest",
    )
    molit_item = PublicPressRelease(
        title="국토교통부 최신 자료",
        publisher="국토교통부",
        published_at="2026-07-20",
        source_url="https://www.korea.kr/molit-latest",
    )
    monkeypatch.setattr(
        public_press_releases,
        "fetch_hug_press_releases",
        lambda *, pattern_id, limit: (hug_item,)[:limit],
    )
    monkeypatch.setattr(
        public_press_releases,
        "fetch_molit_press_releases",
        lambda *, pattern_id, limit: (molit_item,)[:limit],
    )

    items = fetch_recent_press_releases(pattern_id="DP01", limit=2)

    assert [item.publisher for item in items] == [
        "국토교통부",
        "주택도시보증공사(HUG)",
    ]


def test_combined_results_keep_working_source_when_other_source_fails(monkeypatch):
    hug_item = PublicPressRelease(
        title="HUG 자료",
        publisher="주택도시보증공사(HUG)",
        published_at="2026-07-15",
        source_url="https://www.khug.or.kr/hug",
    )
    monkeypatch.setattr(
        public_press_releases,
        "fetch_hug_press_releases",
        lambda *, pattern_id, limit: (hug_item,)[:limit],
    )

    def fail_molit(*, pattern_id: str, limit: int):
        del pattern_id, limit
        raise PublicPressReleaseSourceError("unavailable")

    monkeypatch.setattr(
        public_press_releases,
        "fetch_molit_press_releases",
        fail_molit,
    )

    assert fetch_recent_press_releases(pattern_id="DP01", limit=2) == (hug_item,)


def test_combined_results_fail_only_when_both_sources_fail(monkeypatch):
    def fail(*, pattern_id: str, limit: int):
        del pattern_id, limit
        raise PublicPressReleaseSourceError("unavailable")

    monkeypatch.setattr(public_press_releases, "fetch_hug_press_releases", fail)
    monkeypatch.setattr(public_press_releases, "fetch_molit_press_releases", fail)

    with pytest.raises(PublicPressReleaseSourceError):
        fetch_recent_press_releases(pattern_id="DP01", limit=2)


def test_pattern_rules_use_different_search_queries():
    assert public_press_releases.PATTERN_SEARCH_RULES["DP01"].query == "가짜 임대인"
    assert public_press_releases.PATTERN_SEARCH_RULES["DP05"].query == "신탁주택 전세"
    assert public_press_releases.PATTERN_SEARCH_RULES["DP08"].query == "보증금 미반환"
