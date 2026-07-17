"""사용자 피드백 API — 등록·이력 조회·검증·접근 통제."""

# ruff: noqa: E402 -- 테스트 DB 환경변수를 app import 전에 설정해야 한다.

import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test_feedback.db"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-bytes-long"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _token(client, username):
    client.post(
        "/api/auth/signup",
        json={"username": username, "email": f"{username}@test.com", "password": "password1!"},
    )
    res = client.post("/api/auth/login", json={"username": username, "password": "password1!"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def alice(client):
    return _token(client, "alice")


@pytest.fixture(scope="module")
def contract_id(client, alice):
    return client.post("/api/contracts", json={"title": "피드백용"}, headers=alice).json()["id"]


def test_create_and_list_history(client, alice, contract_id):
    res = client.post(
        f"/api/contracts/{contract_id}/feedback",
        json={"content": "질문 문구가 이해하기 쉬웠어요", "rating": 5},
        headers=alice,
    )
    assert res.status_code == 201
    assert res.json()["rating"] == 5

    # 평점 없이도 등록 가능 — 이력은 최신순으로 쌓임
    res = client.post(
        f"/api/contracts/{contract_id}/feedback",
        json={"content": "등기 연결이 헷갈렸어요"},
        headers=alice,
    )
    assert res.status_code == 201
    assert res.json()["rating"] is None

    items = client.get(f"/api/contracts/{contract_id}/feedback", headers=alice).json()
    assert [i["content"] for i in items] == ["등기 연결이 헷갈렸어요", "질문 문구가 이해하기 쉬웠어요"]


def test_validation_422(client, alice, contract_id):
    for body in ({"content": ""}, {"content": "x", "rating": 6}, {"content": "x", "rating": 0}):
        res = client.post(f"/api/contracts/{contract_id}/feedback", json=body, headers=alice)
        assert res.status_code == 422


def test_other_user_cannot_access(client, alice, contract_id):
    bob = _token(client, "bob")
    assert (
        client.post(
            f"/api/contracts/{contract_id}/feedback", json={"content": "x"}, headers=bob
        ).status_code
        == 404
    )
    assert client.get(f"/api/contracts/{contract_id}/feedback", headers=bob).status_code == 404
