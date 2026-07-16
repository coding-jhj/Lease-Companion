import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.mvp_app import app


ROOT = Path(__file__).resolve().parents[3]
client = TestClient(app)


def _document(path: Path) -> dict[str, str]:
    return {
        "filename": path.name,
        "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
    }


def test_extract_review_analyze_flow():
    extraction_response = client.post(
        "/api/minimum-mvp/extract",
        json={
            "contract": _document(ROOT / "data/sample/contracts/contract_001.txt"),
            "registry": _document(ROOT / "data/sample/registry-records/registry_001.txt"),
        },
    )
    assert extraction_response.status_code == 200
    extraction = extraction_response.json()

    not_confirmed = client.post(
        "/api/minimum-mvp/analyze",
        json={
            "contract_fields": extraction["contract"]["fields"],
            "registry_fields": extraction["registry"]["fields"],
            "user_confirmed": False,
        },
    )
    assert not_confirmed.status_code == 422

    analysis_response = client.post(
        "/api/minimum-mvp/analyze",
        json={
            "contract_fields": extraction["contract"]["fields"],
            "registry_fields": extraction["registry"]["fields"],
            "user_confirmed": True,
        },
    )
    assert analysis_response.status_code == 200
    payload = analysis_response.json()
    assert len(payload["results"]) == 10
    assert "안전" in payload["disclaimer"]


def test_home_serves_demo():
    response = client.get("/")
    assert response.status_code == 200
    assert "추출값 확인·수정" in response.text


def test_analyze_rejects_wrong_canonical_field_type_as_422():
    response = client.post(
        "/api/minimum-mvp/analyze",
        json={
            "contract_fields": {"landlord_name": 123},
            "registry_fields": {"owner_names": ["박성우"]},
            "user_confirmed": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "extraction_not_confirmed"


def test_validation_error_does_not_echo_uploaded_content():
    secret = "SECRET_BASE64_DOCUMENT_BODY"
    response = client.post(
        "/api/minimum-mvp/extract",
        json={"contract": {"filename": "x.txt", "content_base64": secret}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert secret not in response.text
