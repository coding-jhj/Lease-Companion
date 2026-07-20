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


def test_situation_full_context_fields(client, alice):
    """통합 ContractContext 나머지 필드 저장·재조회 (기존 2필드 요청도 그대로 동작)."""
    cid = client.post("/api/contracts", json={"title": "전체상황입력용"}, headers=alice).json()["id"]
    res = client.put(
        f"/api/contracts/{cid}/situation",
        json={
            "contract_type": "전세",
            "contract_stage": "서명 전",
            "deposit_paid": False,
            "signed": False,
            "move_in_date": "2026-09-01",
            "balance_payment_date": "2026-08-30",
            "is_proxy_contract": None,
        },
        headers=alice,
    )
    assert res.status_code == 200
    body = client.get(f"/api/contracts/{cid}", headers=alice).json()
    assert body["deposit_paid"] is False
    assert body["move_in_date"] == "2026-09-01"
    assert body["balance_payment_date"] == "2026-08-30"
    assert body["is_proxy_contract"] is None


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


def test_dashboard_action_status_reflects_checklist_completion(client, alice):
    from app.core.db import SessionLocal
    from app.models.analysis import STATUS_COMPLETED, AnalysisRun

    cid = client.post("/api/contracts", json={"title": "행동상태용"}, headers=alice).json()["id"]
    generation_result = {
        "items": [
            {
                "signing_checklist_items": [{"item_key": "R01:checklist:aaaaaaaaaaaa"}],
                "post_contract_action_items": [{"item_key": "R01:post_action:bbbbbbbbbbbb"}],
            }
        ],
        "judgment_items": [],
    }
    with SessionLocal() as db:
        db.add(
            AnalysisRun(
                contract_id=cid,
                analysis_run_id="RUN-DASH-1",
                input_snapshot_id="SNAP-DASH-1",
                status=STATUS_COMPLETED,
                input_snapshot={},
                result={},
                generation_result=generation_result,
            )
        )
        db.commit()

    def action_status() -> str:
        contracts = client.get("/api/contracts", headers=alice).json()
        return next(c for c in contracts if c["id"] == cid)["action_status"]

    assert action_status() == "none"  # 아무 항목도 완료 안 함

    client.put(
        f"/api/contracts/{cid}/checklist-items/checklist/R01:checklist:aaaaaaaaaaaa",
        json={"done": True}, headers=alice,
    )
    assert action_status() == "in_progress"  # 둘 중 하나만 완료

    client.put(
        f"/api/contracts/{cid}/checklist-items/post_action/R01:post_action:bbbbbbbbbbbb",
        json={"done": True}, headers=alice,
    )
    assert action_status() == "done"  # 체크리스트+행동 전부 완료


def test_requires_auth(client):
    assert client.get("/api/contracts").status_code == 401
    assert client.post("/api/contracts", json={"title": "x"}).status_code == 401
