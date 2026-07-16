"""계약 건 API 테스트: 생성·목록·상세·상황 입력·삭제·접근 통제."""

import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test_contracts.db"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-bytes-long"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.contract import ContractStage as BackendContractStage
from app.schemas.contract import ContractType as BackendContractType
from lease_companion_ai.schemas.unified import ContractStage, ContractType


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
def bob(client):
    return _token(client, "bob")


def test_create_and_get(client, alice):
    res = client.post("/api/contracts", json={"title": "행복빌라 302호 전세"}, headers=alice)
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "행복빌라 302호 전세"
    assert body["contract_type"] is None  # 상황 입력 전

    res = client.get(f"/api/contracts/{body['id']}", headers=alice)
    assert res.status_code == 200


def test_list_own_only(client, alice, bob):
    client.post("/api/contracts", json={"title": "bob의 계약"}, headers=bob)
    titles = [c["title"] for c in client.get("/api/contracts", headers=alice).json()]
    assert "bob의 계약" not in titles
    assert "행복빌라 302호 전세" in titles


def test_situation_input(client, alice):
    cid = client.post("/api/contracts", json={"title": "상황입력용"}, headers=alice).json()["id"]
    res = client.put(
        f"/api/contracts/{cid}/situation",
        json={"contract_type": "보증부 월세", "contract_stage": "계약금 입금 전"},
        headers=alice,
    )
    assert res.status_code == 200
    assert res.json()["contract_type"] == "보증부 월세"
    assert res.json()["contract_stage"] == "계약금 입금 전"


def test_backend_reuses_canonical_contract_enums():
    assert BackendContractType is ContractType
    assert BackendContractStage is ContractStage


def test_situation_invalid_stage(client, alice):
    cid = client.post("/api/contracts", json={"title": "단계검증용"}, headers=alice).json()["id"]
    res = client.put(
        f"/api/contracts/{cid}/situation",
        json={"contract_type": "전세", "contract_stage": "매물 보는 중"},
        headers=alice,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_situation_invalid_type(client, alice):
    cid = client.post("/api/contracts", json={"title": "유형검증용"}, headers=alice).json()["id"]
    res = client.put(
        f"/api/contracts/{cid}/situation",
        json={"contract_type": "상가 임대", "contract_stage": "계약 전"},
        headers=alice,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_other_users_contract_hidden(client, alice, bob):
    cid = client.post("/api/contracts", json={"title": "alice만 봄"}, headers=alice).json()["id"]
    assert client.get(f"/api/contracts/{cid}", headers=bob).status_code == 404
    assert client.delete(f"/api/contracts/{cid}", headers=bob).status_code == 404


def test_delete(client, alice):
    cid = client.post("/api/contracts", json={"title": "삭제용"}, headers=alice).json()["id"]
    assert client.delete(f"/api/contracts/{cid}", headers=alice).status_code == 204
    assert client.get(f"/api/contracts/{cid}", headers=alice).status_code == 404


def test_requires_auth(client):
    assert client.get("/api/contracts").status_code == 401
    assert client.post("/api/contracts", json={"title": "x"}).status_code == 401
