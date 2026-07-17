"""체크리스트·계약 직후 행동 상태 API 테스트 — 저장·재조회·접근 통제."""

# ruff: noqa: E402 -- 테스트 DB 환경변수를 app import 전에 설정해야 한다.

import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test_checklists.db"
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
    return client.post("/api/contracts", json={"title": "체크리스트용"}, headers=alice).json()["id"]


def test_upsert_and_requery(client, alice, contract_id):
    res = client.put(
        f"/api/contracts/{contract_id}/checklist-items/checklist/R01",
        json={"done": True},
        headers=alice,
    )
    assert res.status_code == 200
    assert res.json() == {**res.json(), "kind": "checklist", "item_key": "R01", "done": True}

    # 같은 항목 갱신 — 새 행이 아니라 덮어씀
    res = client.put(
        f"/api/contracts/{contract_id}/checklist-items/checklist/R01",
        json={"done": False},
        headers=alice,
    )
    assert res.json()["done"] is False

    client.put(
        f"/api/contracts/{contract_id}/checklist-items/post_action/confirmed-date",
        json={"done": True},
        headers=alice,
    )

    items = client.get(f"/api/contracts/{contract_id}/checklist-items", headers=alice).json()
    assert len(items) == 2

    # kind 필터
    post = client.get(
        f"/api/contracts/{contract_id}/checklist-items", params={"kind": "post_action"}, headers=alice
    ).json()
    assert [i["item_key"] for i in post] == ["confirmed-date"]


def test_invalid_kind_rejected(client, alice, contract_id):
    res = client.put(
        f"/api/contracts/{contract_id}/checklist-items/bogus/R01",
        json={"done": True},
        headers=alice,
    )
    assert res.status_code == 422


def test_other_user_cannot_access(client, contract_id):
    bob = _token(client, "bob")
    assert client.get(f"/api/contracts/{contract_id}/checklist-items", headers=bob).status_code == 404
    res = client.put(
        f"/api/contracts/{contract_id}/checklist-items/checklist/R01",
        json={"done": True},
        headers=bob,
    )
    assert res.status_code == 404
