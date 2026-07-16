"""문서 업로드·이력·모의 등기 연결 테스트."""

import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test_documents.db"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-bytes-long"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["REGISTRY_DIR"] = f"{_tmp}/registry"

import pathlib

import pytest
from fastapi.testclient import TestClient

from app.main import app

# 모의 등기 fixture 흉내 (CASE-001 존재, 그 외 없음)
pathlib.Path(f"{_tmp}/registry").mkdir()
pathlib.Path(f"{_tmp}/registry/registry_CASE-001.txt").write_text("mock", encoding="utf-8")

PDF = ("contract.pdf", b"%PDF-1.4 fake", "application/pdf")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def owner(client):
    client.post(
        "/api/auth/signup",
        json={"username": "docuser", "email": "doc@test.com", "password": "password1!"},
    )
    res = client.post("/api/auth/login", json={"username": "docuser", "password": "password1!"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture(scope="module")
def contract_id(client, owner):
    return client.post("/api/contracts", json={"title": "업로드 테스트"}, headers=owner).json()["id"]


def test_upload_pdf(client, owner, contract_id):
    res = client.post(
        f"/api/contracts/{contract_id}/documents",
        files={"file": PDF},
        data={"doc_type": "계약서"},
        headers=owner,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["doc_type"] == "계약서"
    assert body["filename"] == "contract.pdf"
    assert body["size_bytes"] > 0


def test_upload_rejects_bad_extension(client, owner, contract_id):
    res = client.post(
        f"/api/contracts/{contract_id}/documents",
        files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
        data={"doc_type": "계약서"},
        headers=owner,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "unsupported_file_type"


def test_upload_rejects_empty_file(client, owner, contract_id):
    res = client.post(
        f"/api/contracts/{contract_id}/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"doc_type": "계약서"},
        headers=owner,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "empty_file"


def test_upload_rejects_bad_doc_type(client, owner, contract_id):
    res = client.post(
        f"/api/contracts/{contract_id}/documents",
        files={"file": PDF},
        data={"doc_type": "주민등록등본"},
        headers=owner,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_history_keeps_reuploads(client, owner, contract_id):
    client.post(
        f"/api/contracts/{contract_id}/documents",
        files={"file": ("contract_v2.pdf", b"%PDF-1.4 v2", "application/pdf")},
        data={"doc_type": "계약서"},
        headers=owner,
    )
    docs = client.get(f"/api/contracts/{contract_id}/documents", headers=owner).json()
    names = [d["filename"] for d in docs]
    assert "contract.pdf" in names and "contract_v2.pdf" in names  # 이력 유지
    assert docs[0]["filename"] == "contract_v2.pdf"  # 최신순


def test_registry_link(client, owner, contract_id):
    res = client.post(
        f"/api/contracts/{contract_id}/registry-link",
        json={"case_id": "CASE-001"},
        headers=owner,
    )
    assert res.status_code == 200
    assert res.json()["registry_case_id"] == "CASE-001"


def test_registry_link_unknown_case(client, owner, contract_id):
    res = client.post(
        f"/api/contracts/{contract_id}/registry-link",
        json={"case_id": "CASE-999"},
        headers=owner,
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_other_user_cannot_upload_or_list(client, contract_id):
    client.post(
        "/api/auth/signup",
        json={"username": "intruder", "email": "int@test.com", "password": "password1!"},
    )
    res = client.post("/api/auth/login", json={"username": "intruder", "password": "password1!"})
    other = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert client.get(f"/api/contracts/{contract_id}/documents", headers=other).status_code == 404
    res = client.post(
        f"/api/contracts/{contract_id}/documents",
        files={"file": PDF},
        data={"doc_type": "계약서"},
        headers=other,
    )
    assert res.status_code == 404
