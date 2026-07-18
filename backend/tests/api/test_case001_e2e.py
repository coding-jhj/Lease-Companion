"""CASE-001 8단계 end-to-end 시나리오 (진행순서 문서 4단계 통합 검증의 백엔드 몫).

회원가입 → 로그인 → 계약 건 생성 → 상황 입력 → 계약서 업로드 + 모의 등기 연결(registry-link)
→ 추출 → 수정 → 확인 → 분석 폴링 → 리포트 → 체크리스트 → **재로그인 후 재조회**.

test_analyses.py가 API 단위 검증이라면 여기는 실제 사용자 흐름 순서 그대로 한 번에 통과하는지 본다.
"""

# ruff: noqa: E402 -- 테스트 DB 환경변수를 app import 전에 설정해야 한다.

import json
import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test_case001_e2e.db"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-bytes-long"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"

import pytest
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_TXT = ROOT / "data" / "sample" / "contracts" / "contract_001.txt"
CORRECTION_FIXTURE = ROOT / "data" / "sample" / "fixtures" / "case-001" / "correction_request.json"

USERNAME, PASSWORD = "case001_user", "password1!"


def _login(client):
    res = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_case001_full_flow(client):
    # 1. 회원가입 → 로그인 (합의: 가입은 토큰을 주지 않음 — 별도 로그인)
    res = client.post(
        "/api/auth/signup",
        json={"username": USERNAME, "email": f"{USERNAME}@test.com", "password": PASSWORD},
    )
    assert res.status_code == 201
    assert "access_token" not in res.json()
    auth = _login(client)

    # 2. 계약 건 생성
    cid = client.post("/api/contracts", json={"title": "CASE-001 통합"}, headers=auth).json()["id"]

    # 3. 계약 상황 입력 (통합 ContractContext 전체 필드)
    res = client.put(
        f"/api/contracts/{cid}/situation",
        json={
            "contract_type": "전세",
            "contract_stage": "서명 전",
            "deposit_paid": False,
            "signed": False,
            "move_in_date": "2026-09-01",
            "balance_payment_date": "2026-08-30",
            "is_proxy_contract": False,
        },
        headers=auth,
    )
    assert res.status_code == 200

    # 4. 계약서 업로드 + 모의 등기 연결
    with CONTRACT_TXT.open("rb") as f:
        res = client.post(
            f"/api/contracts/{cid}/documents",
            files={"file": (CONTRACT_TXT.name, f, "text/plain")},
            data={"doc_type": "계약서"},
            headers=auth,
        )
    assert res.status_code == 201
    res = client.post(f"/api/contracts/{cid}/registry-link", json={"case_id": "CASE-001"}, headers=auth)
    assert res.status_code == 200
    assert res.json()["registry_case_id"] == "CASE-001"

    # 5. 추출 실행 → 폴링 → 수정 → 확인 (사용자 흐름 5단계)
    assert client.post(f"/api/contracts/{cid}/extractions", headers=auth).status_code == 202
    state = client.get(f"/api/contracts/{cid}/extractions/latest", headers=auth).json()
    assert state["status"] == "completed", state.get("error")

    correction = json.loads(CORRECTION_FIXTURE.read_text(encoding="utf-8"))
    correction["contract_id"] = cid
    assert client.post(f"/api/contracts/{cid}/corrections", json=correction, headers=auth).status_code == 201
    assert client.post(f"/api/contracts/{cid}/extractions/confirm", headers=auth).status_code == 201

    # 6~7. 분석 실행 → 폴링 → 리포트
    run_id = client.post(f"/api/contracts/{cid}/analysis-runs", headers=auth).json()["analysis_run_id"]
    detail = client.get(f"/api/contracts/{cid}/analysis-runs/{run_id}", headers=auth).json()
    assert detail["status"] == "completed", detail.get("error")
    results = detail["result"]["results"]
    assert [r["rule_id"] for r in results] == [f"R{i:02d}" for i in range(1, 11)]
    # 생성 결과 분리 저장 — 키 없는 오프라인 실행도 template fallback으로 완료
    assert detail["generation_status"] == "completed"
    assert detail["generation_result"]["guardrail_passed"] is True
    # 통합 검증 항목: 단정 문구가 저장 결과 어디에도 없어야 한다
    assert "안전합니다" not in json.dumps(detail["result"], ensure_ascii=False)

    # 8. 체크리스트 상태 저장
    checklist_item = next(
        item
        for guidance in detail["generation_result"]["items"]
        for item in guidance["signing_checklist_items"]
    )
    checklist_item_key = checklist_item["item_key"]
    res = client.put(
        f"/api/contracts/{cid}/checklist-items/checklist/{checklist_item_key}",
        json={"done": True},
        headers=auth,
    )
    assert res.status_code == 200

    # 재로그인(새 토큰) 후에도 리포트·체크리스트가 다시 열리는가 (통합 검증 항목)
    auth2 = _login(client)
    history = client.get(f"/api/contracts/{cid}/analysis-runs", headers=auth2).json()
    assert history and history[0]["status"] == "completed"
    detail2 = client.get(f"/api/contracts/{cid}/analysis-runs/{run_id}", headers=auth2).json()
    assert detail2["result"] == detail["result"]
    items = client.get(f"/api/contracts/{cid}/checklist-items", headers=auth2).json()
    assert [(i["kind"], i["item_key"], i["done"]) for i in items] == [("checklist", checklist_item_key, True)]
