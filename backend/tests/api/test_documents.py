"""문서 업로드·이력·모의 등기 연결 테스트."""

# ruff: noqa: E402 -- 테스트 DB 환경변수를 app import 전에 설정해야 한다.

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
        json={"username": "docuser", "email": "doc@test.com", "password": "Password1!"},
    )
    res = client.post("/api/auth/login", json={"username": "docuser", "password": "Password1!"})
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


def test_uploaded_file_is_encrypted_at_rest(client, owner, contract_id):
    """평문 원본이 디스크에 남지 않아야 한다 (기획서: 개인정보는 암호화해서 저장)."""
    secret = b"%PDF-1.4 landlord 010-1234-5678"
    client.post(
        f"/api/contracts/{contract_id}/documents",
        files={"file": ("secret.pdf", secret, "application/pdf")},
        data={"doc_type": "계약서"},
        headers=owner,
    )
    # 수집 시점에 다른 테스트 모듈이 UPLOAD_DIR을 덮어쓸 수 있어 실행 시점 값을 읽는다.
    stored = list(pathlib.Path(os.environ["UPLOAD_DIR"]).iterdir())
    assert stored, "업로드 파일이 저장되지 않았습니다."
    assert all(path.suffix == ".enc" for path in stored)
    assert not any(secret in path.read_bytes() for path in stored)


def test_evidence_upload_list_download_delete(client, owner, contract_id):
    """증빙 보관: 업로드 → 목록 분리 → 원본 내려받기 → 삭제."""
    receipt = b"%PDF-1.4 transfer receipt"
    created = client.post(
        f"/api/contracts/{contract_id}/documents",
        files={"file": ("receipt.pdf", receipt, "application/pdf")},
        data={"doc_type": "이체내역"},
        headers=owner,
    )
    assert created.status_code == 201
    document_id = created.json()["id"]

    evidence = client.get(
        f"/api/contracts/{contract_id}/documents?kind=evidence", headers=owner
    ).json()
    assert [d["doc_type"] for d in evidence] == ["이체내역"]
    analysis_docs = client.get(
        f"/api/contracts/{contract_id}/documents?kind=analysis", headers=owner
    ).json()
    assert "이체내역" not in {d["doc_type"] for d in analysis_docs}

    downloaded = client.get(
        f"/api/contracts/{contract_id}/documents/{document_id}/file", headers=owner
    )
    assert downloaded.status_code == 200
    assert downloaded.content == receipt  # 복호화해서 원본 그대로 돌려준다

    assert client.delete(
        f"/api/contracts/{contract_id}/documents/{document_id}", headers=owner
    ).status_code == 204
    assert client.get(
        f"/api/contracts/{contract_id}/documents?kind=evidence", headers=owner
    ).json() == []


def test_analysis_document_cannot_be_deleted(client, owner, contract_id):
    created = client.post(
        f"/api/contracts/{contract_id}/documents",
        files={"file": PDF},
        data={"doc_type": "계약서"},
        headers=owner,
    ).json()
    res = client.delete(
        f"/api/contracts/{contract_id}/documents/{created['id']}", headers=owner
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "not_evidence_document"


def test_other_user_cannot_upload_or_list(client, contract_id):
    client.post(
        "/api/auth/signup",
        json={"username": "intruder", "email": "int@test.com", "password": "Password1!"},
    )
    res = client.post("/api/auth/login", json={"username": "intruder", "password": "Password1!"})
    other = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert client.get(f"/api/contracts/{contract_id}/documents", headers=other).status_code == 404
    res = client.post(
        f"/api/contracts/{contract_id}/documents",
        files={"file": PDF},
        data={"doc_type": "계약서"},
        headers=other,
    )
    assert res.status_code == 404
