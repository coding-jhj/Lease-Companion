"""추출(비동기)→수정→확인→분석(비동기)→재조회 전체 흐름 테스트.

CASE-001 correction fixture와 합성 샘플 문서를 입력으로 사용한다.
TestClient는 BackgroundTasks를 요청 처리 중 동기 실행하므로 폴링 GET에서 곧바로 완료 상태를 본다.
"""

# ruff: noqa: E402 -- 테스트 DB 환경변수를 app import 전에 설정해야 한다.

import json
import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test_analyses.db"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-bytes-long"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from lease_companion_ai.schemas.unified import SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_TXT = ROOT / "data" / "sample" / "contracts" / "contract_001.txt"
REGISTRY_TXT = ROOT / "data" / "sample" / "registry-records" / "registry_001.txt"
CORRECTION_FIXTURE = ROOT / "data" / "sample" / "fixtures" / "case-001" / "correction_request.json"


def _token(client, username):
    client.post(
        "/api/auth/signup",
        json={"username": username, "email": f"{username}@test.com", "password": "password1!"},
    )
    res = client.post("/api/auth/login", json={"username": username, "password": "password1!"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _upload(client, headers, contract_id, path, doc_type):
    with path.open("rb") as f:
        res = client.post(
            f"/api/contracts/{contract_id}/documents",
            files={"file": (path.name, f, "text/plain")},
            data={"doc_type": doc_type},
            headers=headers,
        )
    assert res.status_code == 201


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def alice(client):
    return _token(client, "alice")


SITUATION = {
    "contract_type": "전세",
    "contract_stage": "서명 전",
    "deposit_paid": False,
    "signed": False,
    "is_proxy_contract": False,
}


@pytest.fixture(scope="module")
def contract_id(client, alice):
    """상황 입력·문서 업로드·추출·수정·확인까지 끝난 계약 건 — 모듈 내 분석 테스트의 공통 전제."""
    cid = client.post("/api/contracts", json={"title": "분석용"}, headers=alice).json()["id"]
    assert client.put(f"/api/contracts/{cid}/situation", json=SITUATION, headers=alice).status_code == 200
    _upload(client, alice, cid, CONTRACT_TXT, "계약서")
    _upload(client, alice, cid, REGISTRY_TXT, "등기사항증명서")

    res = client.post(f"/api/contracts/{cid}/extractions", headers=alice)
    assert res.status_code == 202
    assert res.json()["status"] == "pending"

    # 폴링 — TestClient에선 백그라운드 작업이 이미 끝나 있음
    state = client.get(f"/api/contracts/{cid}/extractions/latest", headers=alice).json()
    assert state["status"] == "completed", state.get("error")
    assert "landlord_name" in state["contract_doc"]["fields"]

    correction = json.loads(CORRECTION_FIXTURE.read_text(encoding="utf-8"))
    correction["contract_id"] = cid  # fixture는 1001 — 실제 계약 건 id로 맞춤
    res = client.post(f"/api/contracts/{cid}/corrections", json=correction, headers=alice)
    assert res.status_code == 201
    field = res.json()["contract_doc"]["fields"]["account_holder"]
    # B 인수 체크리스트: 최초 추출값과 수정값 분리 보존
    assert field["user_corrected_value"] == "이정훈"
    assert field["verification_status"] == "corrected"

    res = client.post(f"/api/contracts/{cid}/extractions/confirm", headers=alice)
    assert res.status_code == 201
    body = res.json()
    assert body["input_snapshot_id"].startswith("snap-")
    # A 확정(2026-07-17): 스냅샷에 계약 상황이 불변 포함 + 응답에 canonical payload 전체
    ctx = body["snapshot"]["contract_context"]
    assert ctx["contract_type"] == "전세"
    assert ctx["contract_id"] == cid
    return cid


def test_correction_preserves_original(client, alice, contract_id):
    """수정을 다시 적용해도 원본 extracted_value는 절대 덮이지 않는다."""
    before = client.get(f"/api/contracts/{contract_id}/extractions/latest", headers=alice).json()
    original = before["contract_doc"]["fields"]["landlord_name"]["extracted_value"]

    res = client.post(
        f"/api/contracts/{contract_id}/corrections",
        json={
            "contract_id": contract_id,
            "corrections": [
                {"document_type": "contract", "field_name": "landlord_name", "corrected_value": "수정된이름"}
            ],
            "schema_version": SCHEMA_VERSION,
        },
        headers=alice,
    )
    assert res.status_code == 201
    field = res.json()["contract_doc"]["fields"]["landlord_name"]
    assert field["user_corrected_value"] == "수정된이름"
    assert field["extracted_value"] == original  # 원본 보존
    assert field["verification_status"] == "corrected"


def test_analysis_run_poll_and_reload(client, alice, contract_id):
    res = client.post(f"/api/contracts/{contract_id}/analysis-runs", headers=alice)
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "pending"
    assert body["result"] is None
    run_id = body["analysis_run_id"]

    # 폴링
    res = client.get(f"/api/contracts/{contract_id}/analysis-runs/{run_id}", headers=alice)
    detail = res.json()
    assert detail["status"] == "completed", detail.get("error")
    assert len(detail["result"]["results"]) == 24
    assert [item["judgment_id"] for item in detail["result"]["judgments"]] == [
        f"J{index:02d}" for index in range(1, 13)
    ]
    # 생성 결과 분리 저장(2026-07-17 합의): provider 키 없으면 template fallback으로 정상 완료
    assert detail["generation_status"] == "completed"
    assert detail["generation_error"] is None
    generation = detail["generation_result"]
    assert generation["analysis_run_id"] == run_id
    assert generation["prompt_version"] == "v2"
    assert generation["guardrail_passed"] is True
    stage_guidance = generation["stage_guidance"]
    assert stage_guidance["contract_context"]["contract_stage"] == "서명 전"
    assert stage_guidance["contract_context"]["deposit_paid"] is False
    assert stage_guidance["contract_context"]["signed"] is False
    assert stage_guidance["signing_checklist"]
    assert stage_guidance["post_contract_actions"] == []
    result_rule_ids = {r["rule_id"] for r in detail["result"]["results"]}
    for item in generation["items"]:
        assert item["rule_id"] in result_rule_ids
        assert item["generation_method"] == "template_fallback"  # 키 없는 오프라인 실행

    # 저장 → 조회 → canonical 재검증 왕복 (B 인수 체크리스트)
    from lease_companion_ai.schemas.unified import AnalysisRunResult

    reloaded = AnalysisRunResult.model_validate(detail["result"])
    assert reloaded.analysis_run_id == run_id
    assert len(reloaded.judgments) == 12
    # 수정값이 규칙 입력에 반영됐는지 — R06(계좌 명의)이 확인 불가/확인 필요가 아님
    r06 = next(r for r in reloaded.results if r.rule_id == "R06")
    assert r06.status.value in {"일치", "불일치"}


def test_rerun_appends_history(client, alice, contract_id):
    first = client.get(f"/api/contracts/{contract_id}/analysis-runs", headers=alice).json()
    assert client.post(f"/api/contracts/{contract_id}/analysis-runs", headers=alice).status_code == 202
    history = client.get(f"/api/contracts/{contract_id}/analysis-runs", headers=alice).json()
    assert len(history) == len(first) + 1
    assert all(run["status"] == "completed" for run in history)


def test_classification_persisted_internally_and_not_exposed(
    client, alice, contract_id, monkeypatch
):
    """분석 실행이 classification을 저장하되 API 응답에는 노출하지 않는다 (BC §B-4).

    provider 없음 경계에서는 safe_fallback(후보 없음)으로 흡수되고,
    분석 전체는 정상 completed가 된다. classification_result·error는 내부 저장 전용.
    """
    import app.workers.analysis as worker

    monkeypatch.setattr(worker, "_classification_provider", lambda: None)

    res = client.post(f"/api/contracts/{contract_id}/analysis-runs", headers=alice)
    assert res.status_code == 202
    run_id = res.json()["analysis_run_id"]

    detail = client.get(
        f"/api/contracts/{contract_id}/analysis-runs/{run_id}", headers=alice
    ).json()
    assert detail["status"] == "completed", detail.get("error")
    # 내부 분류 결과는 사용자 응답에 노출하지 않는다.
    assert "classification_result" not in detail
    assert "classification_error" not in detail

    # DB에는 provenance가 저장돼 있어야 한다 — provider 없음 → safe_fallback, 후보 없음.
    from app.core.db import SessionLocal
    from app.models.analysis import AnalysisRun
    from sqlalchemy import select

    with SessionLocal() as db:
        row = db.scalar(
            select(AnalysisRun).where(AnalysisRun.analysis_run_id == run_id)
        )
        assert row.classification_result is not None
        assert row.classification_result["classification_method"] == "safe_fallback"
        assert row.classification_result["fallback_reason_code"] == "provider_unavailable"
        assert row.classification_result["candidates"] == []
        assert row.classification_error is None  # 실패 사유는 fallback_reason_code 단일 원본


class _StubClassificationProvider:
    """입력에 맞춘 유효한 provider 결과를 돌려주는 테스트용 stub (외부 호출 없음)."""

    model_name = "stub-classification"

    def classify(self, classification_input):
        from lease_companion_ai.schemas.unified import (
            ClassificationMethod,
            ClassificationResult,
            ClauseCandidate,
        )

        candidates = []
        if classification_input.clauses:
            ref = classification_input.clauses[0].clause_ref
            candidates = [
                ClauseCandidate(
                    clause_ref=ref,
                    clause_type="other",
                    clarity_candidate="명확",
                    responsible_party_candidate="미지정",
                    condition_candidates=[],
                    review_required=False,
                )
            ]
        return ClassificationResult(
            schema_version=classification_input.schema_version,
            input_snapshot_id=classification_input.input_snapshot_id,
            contract_id=classification_input.contract_id,
            provider_model="stub-classification",
            prompt_version="classification-v1",
            classification_method=ClassificationMethod.PROVIDER,
            candidates=candidates,
        )


class _FailingClassificationProvider:
    """classify가 항상 ProviderError를 던지는 stub — 실패 경계 검증용."""

    model_name = "failing-classification"

    def classify(self, classification_input):
        from lease_companion_ai.providers.errors import ProviderError

        raise ProviderError("stub provider failure")


def _latest_classification_result(run_id):
    from app.core.db import SessionLocal
    from app.models.analysis import AnalysisRun
    from sqlalchemy import select

    with SessionLocal() as db:
        row = db.scalar(select(AnalysisRun).where(AnalysisRun.analysis_run_id == run_id))
        return row.classification_result, row.classification_error, row.status


def test_provider_success_persists_provider_result_not_exposed(
    client, alice, contract_id, monkeypatch
):
    """provider 성공 시 method=provider 결과가 저장되고 API에는 노출되지 않는다."""
    import app.workers.analysis as worker

    monkeypatch.setattr(worker, "_classification_provider", lambda: _StubClassificationProvider())

    run_id = client.post(
        f"/api/contracts/{contract_id}/analysis-runs", headers=alice
    ).json()["analysis_run_id"]
    detail = client.get(
        f"/api/contracts/{contract_id}/analysis-runs/{run_id}", headers=alice
    ).json()

    assert detail["status"] == "completed", detail.get("error")
    assert "classification_result" not in detail  # 미노출
    result, error, status = _latest_classification_result(run_id)
    assert status == "completed"
    assert result["classification_method"] == "provider"
    assert result["fallback_reason_code"] is None
    assert error is None  # 성공 시에도 classification_error는 항상 None
    assert len(result["candidates"]) == 1


def test_provider_failure_falls_back_and_analysis_completes(
    client, alice, contract_id, monkeypatch
):
    """provider 실패는 safe_fallback으로 흡수되고 규칙 분석은 정상 completed가 된다."""
    import app.workers.analysis as worker

    monkeypatch.setattr(worker, "_classification_provider", lambda: _FailingClassificationProvider())

    run_id = client.post(
        f"/api/contracts/{contract_id}/analysis-runs", headers=alice
    ).json()["analysis_run_id"]
    detail = client.get(
        f"/api/contracts/{contract_id}/analysis-runs/{run_id}", headers=alice
    ).json()

    assert detail["status"] == "completed", detail.get("error")
    assert len(detail["result"]["results"]) == 24  # 확장 규칙 분석 정상
    result, error, status = _latest_classification_result(run_id)
    assert status == "completed"
    assert result["classification_method"] == "safe_fallback"
    assert result["fallback_reason_code"] == "provider_error"
    assert error is None  # 실패도 fallback_reason_code에만 — classification_error 중복 저장 금지
    assert result["candidates"] == []


def test_generation_provider_total_failure_falls_back_and_checklist_survives(
    client, alice, contract_id, monkeypatch
):
    """생성 provider가 ProviderError가 아닌 예외로 통째 실패해도(설정·SDK·SSL 등)
    템플릿 폴백으로 체크리스트가 보장된다 — 8번 행동 화면이 비지 않도록."""
    import app.workers.analysis as worker

    class _BoomProvider:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("provider init boom")  # ProviderError 아님

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(worker, "GeminiGenerationProvider", _BoomProvider)
    monkeypatch.setattr(worker, "_classification_provider", lambda: None)

    run_id = client.post(
        f"/api/contracts/{contract_id}/analysis-runs", headers=alice
    ).json()["analysis_run_id"]
    detail = client.get(
        f"/api/contracts/{contract_id}/analysis-runs/{run_id}", headers=alice
    ).json()

    assert detail["status"] == "completed", detail.get("error")
    assert detail["generation_status"] == "completed"  # 폴백으로 완료
    gen = detail["generation_result"]
    assert gen is not None
    checklist_items = [
        item
        for group in (gen["items"] + gen["judgment_items"])
        for item in group["signing_checklist_items"]
    ]
    assert checklist_items  # 최소 1개 체크리스트 보장


def test_analysis_requires_confirmed_snapshot(client, alice):
    cid = client.post("/api/contracts", json={"title": "스냅샷 없음"}, headers=alice).json()["id"]
    res = client.post(f"/api/contracts/{cid}/analysis-runs", headers=alice)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "no_confirmed_snapshot"


def test_extraction_requires_contract_but_registry_is_optional(client, alice):
    cid = client.post("/api/contracts", json={"title": "문서 없음"}, headers=alice).json()["id"]
    res = client.post(f"/api/contracts/{cid}/extractions", headers=alice)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "missing_contract_document"

    _upload(client, alice, cid, CONTRACT_TXT, "계약서")
    res = client.post(f"/api/contracts/{cid}/extractions", headers=alice)
    assert res.status_code == 202
    state = client.get(f"/api/contracts/{cid}/extractions/latest", headers=alice).json()
    assert state["status"] == "completed"
    assert state["registry_doc"]["warnings"] == [
        "등기사항증명서가 없어 관련 항목은 확인 불가로 처리합니다."
    ]


def test_corrections_require_completed_extraction(client, alice):
    cid = client.post("/api/contracts", json={"title": "추출 전"}, headers=alice).json()["id"]
    res = client.post(
        f"/api/contracts/{cid}/corrections",
        json={"contract_id": cid, "corrections": [], "schema_version": SCHEMA_VERSION},
        headers=alice,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "extraction_not_ready"


def test_unknown_correction_field_422(client, alice, contract_id):
    res = client.post(
        f"/api/contracts/{contract_id}/corrections",
        json={
            "contract_id": contract_id,
            "corrections": [
                {"document_type": "contract", "field_name": "no_such_field", "corrected_value": "x"}
            ],
            "schema_version": SCHEMA_VERSION,
        },
        headers=alice,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "unknown_correction_field"


def test_other_user_cannot_access(client, alice, contract_id):
    mallory = _token(client, "mallory")
    assert client.get(f"/api/contracts/{contract_id}/analysis-runs", headers=mallory).status_code == 404
    assert client.get(f"/api/contracts/{contract_id}/extractions/latest", headers=mallory).status_code == 404


def test_run_not_found_404(client, alice, contract_id):
    res = client.get(f"/api/contracts/{contract_id}/analysis-runs/none", headers=alice)
    assert res.status_code == 404


def test_confirm_requires_contract_context(client, alice):
    """계약 상황 미입력 상태의 confirm → 422 (A 확정 오류 코드)."""
    cid = client.post("/api/contracts", json={"title": "상황 미입력"}, headers=alice).json()["id"]
    _upload(client, alice, cid, CONTRACT_TXT, "계약서")
    _upload(client, alice, cid, REGISTRY_TXT, "등기사항증명서")
    assert client.post(f"/api/contracts/{cid}/extractions", headers=alice).status_code == 202
    res = client.post(f"/api/contracts/{cid}/extractions/confirm", headers=alice)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "missing_contract_context"


def test_context_change_blocks_analysis_until_reconfirm(client, alice, contract_id):
    """상황 변경 → 기존 스냅샷 불변 + 분석 차단 → 재확인(새 스냅샷) 후 분석 가능."""
    before = client.post(f"/api/contracts/{contract_id}/extractions/confirm", headers=alice).json()

    changed = dict(SITUATION, contract_stage="계약 직후", signed=True)
    assert client.put(f"/api/contracts/{contract_id}/situation", json=changed, headers=alice).status_code == 200

    # 변경 후 분석 요청 → 차단 (기존 스냅샷은 수정·삭제되지 않음)
    res = client.post(f"/api/contracts/{contract_id}/analysis-runs", headers=alice)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "contract_context_changed"

    # 재확인 → 새 스냅샷 (기존 것과 다른 id, 새 계약 상황 반영) → 분석 가능
    after = client.post(f"/api/contracts/{contract_id}/extractions/confirm", headers=alice).json()
    assert after["input_snapshot_id"] != before["input_snapshot_id"]
    assert after["snapshot"]["contract_context"]["contract_stage"] == "계약 직후"
    assert before["snapshot"]["contract_context"]["contract_stage"] == "서명 전"  # 기존 응답 불변
    res = client.post(f"/api/contracts/{contract_id}/analysis-runs", headers=alice)
    assert res.status_code == 202

    # 원상 복구 (다른 테스트가 같은 계약 건을 공유)
    assert client.put(f"/api/contracts/{contract_id}/situation", json=SITUATION, headers=alice).status_code == 200
    client.post(f"/api/contracts/{contract_id}/extractions/confirm", headers=alice)
