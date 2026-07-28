from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.api.routes import public_cases
from app.core.errors import register_error_handlers
from app.services.public_press_releases import (
    PublicPressRelease,
    PublicPressReleaseSourceError,
)


def _client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(public_cases.router)
    app.dependency_overrides[get_current_user] = lambda: object()
    return TestClient(app)


def test_recent_press_releases_returns_two_source_links(monkeypatch):
    monkeypatch.setattr(
        public_cases,
        "fetch_recent_press_releases",
        lambda pattern_id, limit: (
            PublicPressRelease(
                title="HUG, 전세사기 위험 정보 개방한다",
                publisher="주택도시보증공사(HUG)",
                published_at="2026-07-15",
                source_url=(
                    "https://www.khug.or.kr/khmb/m/hs/nd/"
                    "hsnd000002.jsp?idx=37966"
                ),
            ),
            PublicPressRelease(
                title="전세사기 피해지원 및 예방 확대 업무협약",
                publisher="주택도시보증공사(HUG)",
                published_at="2026-06-10",
                source_url=(
                    "https://www.khug.or.kr/khmb/m/hs/nd/"
                    "hsnd000002.jsp?idx=37757"
                ),
            ),
        )[:limit],
    )

    response = _client().get(
        "/api/public-cases/recent-press-releases?pattern_id=DP01"
    )

    assert response.status_code == 200
    assert response.json()["pattern_id"] == "DP01"
    assert len(response.json()["items"]) == 2
    assert all(
        item["source_url"].startswith("https://www.khug.or.kr/")
        for item in response.json()["items"]
    )
    assert "판정 근거가 아닙니다" in response.json()["notice"]


def test_recent_press_releases_reports_source_failure(monkeypatch):
    def fail(*, pattern_id: str, limit: int):
        del pattern_id, limit
        raise PublicPressReleaseSourceError("source unavailable")

    monkeypatch.setattr(public_cases, "fetch_recent_press_releases", fail)

    response = _client().get(
        "/api/public-cases/recent-press-releases?pattern_id=DP01"
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "public_source_unavailable"


def test_recent_press_releases_rejects_unknown_pattern_id():
    response = _client().get(
        "/api/public-cases/recent-press-releases?pattern_id=DP99"
    )

    assert response.status_code == 422
