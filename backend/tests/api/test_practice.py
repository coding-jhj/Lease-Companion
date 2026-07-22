"""계약 연습 시나리오 3개의 인증·상태 전이·저장 API 회귀 테스트."""

from itertools import count
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test_practice.db")
os.environ.setdefault("JWT_SECRET", "practice-test-secret-at-least-32-bytes")
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""
os.environ["COHERE_API_KEY"] = ""
os.environ["PRACTICE_OFFLINE_MODE"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.practice import (
    APPROVED_SCENARIO_IDS,
    load_approved_practice_assets,
)

_users = count(1)

FREE_FORM_TURN_ONE = (
    (
        "PRACTICE-DEFERRED-REFUND-001",
        "다음 세입자가 안 들어오면 계약이 끝나도 보증금을 못 돌려받는 조건인지 확인할게요.",
    ),
    (
        "PRACTICE-THIRD-PARTY-PAYMENT-001",
        "계좌 명의가 소유자인 임대인이 아니라 중개사인 이유를 확인할게요.",
    ),
    (
        "PRACTICE-PROXY-AUTHORITY-001",
        "등기상 소유자와 지금 나온 대리인이 어떤 관계인지 확인하겠습니다.",
    ),
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _headers(client: TestClient) -> dict[str, str]:
    user_no = next(_users)
    username = f"practice_{user_no}"
    password = "password1!"
    signup = client.post(
        "/api/auth/signup",
        json={
            "username": username,
            "email": f"practice_{user_no}@test.com",
            "password": password,
        },
    )
    assert signup.status_code == 201, signup.text
    login = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_session(client: TestClient, headers: dict[str, str], scenario_id: str) -> dict:
    response = client.post(
        "/api/practice-sessions",
        headers=headers,
        json={"scenario_id": scenario_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _example(answer_key, turn_id: str, status: str):
    return next(
        item
        for item in answer_key.evaluation_examples
        if item.turn_id == turn_id and item.expected_status_id == status and item.user_input is not None
    )


def _timeout_example(answer_key, turn_id: str):
    return next(
        item
        for item in answer_key.evaluation_examples
        if item.turn_id == turn_id and item.input_context.provider_error == "timeout"
    )


def test_practice_endpoints_require_login(client: TestClient):
    paths = [
        "/api/practice-scenarios",
        f"/api/practice-scenarios/{APPROVED_SCENARIO_IDS[0]}",
        "/api/practice-sessions/not-owned",
        "/api/practice-sessions/not-owned/result",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"


def test_scenario_list_and_detail_hide_internal_answers(client: TestClient):
    headers = _headers(client)
    listed = client.get("/api/practice-scenarios", headers=headers)
    assert listed.status_code == 200
    assert [item["scenario_id"] for item in listed.json()] == list(APPROVED_SCENARIO_IDS)

    forbidden_fields = (
        "hidden_confirmation_signals",
        "target_actions",
        "required_semantics",
        "partial_semantics",
        "not_sufficient",
        "evaluation_examples",
        "rule_states",
        "judgment_states",
    )
    for scenario_id in APPROVED_SCENARIO_IDS:
        scenario, _ = load_approved_practice_assets(scenario_id)
        response = client.get(f"/api/practice-scenarios/{scenario_id}", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["initial_turn"]["turn_id"] == scenario.dialogue_turns[0].turn_id
        assert payload["initial_turn"]["prompt"] == scenario.dialogue_turns[0].prompt
        assert all(field not in response.text for field in forbidden_fields)
        if len(scenario.dialogue_turns) > 1:
            assert scenario.dialogue_turns[1].prompt not in response.text


def test_unapproved_scenario_is_not_available(client: TestClient):
    headers = _headers(client)
    scenario_id = "PRACTICE-NOT-APPROVED-999"
    detail = client.get(f"/api/practice-scenarios/{scenario_id}", headers=headers)
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "practice_scenario_not_found"

    created = client.post(
        "/api/practice-sessions",
        headers=headers,
        json={"scenario_id": scenario_id},
    )
    assert created.status_code == 404
    assert created.json()["error"]["code"] == "practice_scenario_not_found"


def test_only_owner_can_read_or_submit_to_session(client: TestClient):
    owner_headers = _headers(client)
    other_headers = _headers(client)
    session = _create_session(client, owner_headers, "PRACTICE-DEFERRED-REFUND-001")
    session_id = session["practice_session_id"]

    read = client.get(f"/api/practice-sessions/{session_id}", headers=other_headers)
    assert read.status_code == 404
    assert read.json()["error"]["code"] == "practice_session_not_found"

    submit = client.post(
        f"/api/practice-sessions/{session_id}/turns",
        headers=other_headers,
        json={
            "request_id": "other-user-request",
            "turn_id": "TURN-01",
            "user_answer": "확인하겠습니다.",
            "response_time_seconds": 1,
        },
    )
    assert submit.status_code == 404
    assert submit.json()["error"]["code"] == "practice_session_not_found"

    result = client.get(f"/api/practice-sessions/{session_id}/result", headers=other_headers)
    assert result.status_code == 404


def test_turn_request_validation_and_stale_turn_rejection(client: TestClient):
    headers = _headers(client)
    session = _create_session(client, headers, "PRACTICE-THIRD-PARTY-PAYMENT-001")
    session_id = session["practice_session_id"]
    endpoint = f"/api/practice-sessions/{session_id}/turns"

    missing_answer = client.post(
        endpoint,
        headers=headers,
        json={
            "request_id": "missing-answer-01",
            "turn_id": "TURN-01",
            "response_time_seconds": 1,
        },
    )
    assert missing_answer.status_code == 422

    timeout_with_answer = client.post(
        endpoint,
        headers=headers,
        json={
            "request_id": "timeout-answer-01",
            "turn_id": "TURN-01",
            "user_answer": "답변",
            "timed_out": True,
            "response_time_seconds": 30,
        },
    )
    assert timeout_with_answer.status_code == 422

    stale = client.post(
        endpoint,
        headers=headers,
        json={
            "request_id": "stale-turn-request",
            "turn_id": "TURN-02",
            "user_answer": "두 번째 질문을 먼저 하겠습니다.",
            "response_time_seconds": 1,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "invalid_practice_transition"

    restored = client.get(f"/api/practice-sessions/{session_id}", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["current_state"] == "TURN-01"
    assert restored.json()["confirmed_action_ids"] == []


def test_timed_out_turn_is_saved_as_no_response_and_can_retry(client: TestClient):
    headers = _headers(client)
    session = _create_session(client, headers, "PRACTICE-PROXY-AUTHORITY-001")
    session_id = session["practice_session_id"]
    endpoint = f"/api/practice-sessions/{session_id}/turns"
    response = client.post(
        endpoint,
        headers=headers,
        json={
            "request_id": "timed-out-request",
            "turn_id": "TURN-01",
            "timed_out": True,
            "response_time_seconds": 30,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["attempt_no"] == 1
    assert payload["evaluation"]["answer_category"] == "no_response"
    assert payload["session"]["current_state"] == "TURN-01"
    assert payload["session"]["confirmed_action_ids"] == []


def test_user_can_advance_without_confirming_or_move_to_final_choice(client: TestClient):
    headers = _headers(client)
    session = _create_session(client, headers, "PRACTICE-DEFERRED-REFUND-001")
    session_id = session["practice_session_id"]
    endpoint = f"/api/practice-sessions/{session_id}/advance"

    advanced = client.post(
        endpoint,
        headers=headers,
        json={
            "request_id": "advance-without-confirmation",
            "turn_id": "TURN-01",
            "destination": "next_turn",
        },
    )
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["evaluation"] is None
    assert advanced.json()["session"]["current_state"] == "TURN-02"
    assert advanced.json()["session"]["confirmed_action_ids"] == []

    final_choice = client.post(
        endpoint,
        headers=headers,
        json={
            "request_id": "finish-dialogue-early",
            "turn_id": "TURN-02",
            "destination": "action_selection",
        },
    )
    assert final_choice.status_code == 200, final_choice.text
    assert final_choice.json()["session"]["current_state"] == "ACTION-SELECTION"
    assert final_choice.json()["session"]["confirmed_action_ids"] == []


@pytest.mark.parametrize("scenario_id,user_answer", FREE_FORM_TURN_ONE)
def test_offline_practice_accepts_natural_turn_answer(
    client: TestClient, scenario_id: str, user_answer: str
):
    headers = _headers(client)
    session = _create_session(client, headers, scenario_id)
    session_id = session["practice_session_id"]

    response = client.post(
        f"/api/practice-sessions/{session_id}/turns",
        headers=headers,
        json={
            "request_id": f"free-form-{scenario_id}",
            "turn_id": "TURN-01",
            "user_answer": user_answer,
            "response_time_seconds": 2,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["evaluation"]["answer_category"] == "appropriate_check"
    assert payload["evaluation"]["fallback_reason"] is None
    assert payload["session"]["current_turn"]["turn_id"] == "TURN-02"


@pytest.mark.parametrize("scenario_id", APPROVED_SCENARIO_IDS)
def test_three_scenarios_retry_complete_and_remain_immutable(client: TestClient, scenario_id: str):
    headers = _headers(client)
    scenario, answer_key = load_approved_practice_assets(scenario_id)
    session = _create_session(client, headers, scenario_id)
    session_id = session["practice_session_id"]
    turns_endpoint = f"/api/practice-sessions/{session_id}/turns"

    not_ready = client.get(f"/api/practice-sessions/{session_id}/result", headers=headers)
    assert not_ready.status_code == 409
    assert not_ready.json()["error"]["code"] == "practice_result_not_ready"

    premature_final = client.post(
        f"/api/practice-sessions/{session_id}/final-action",
        headers=headers,
        json={
            "request_id": f"premature-{scenario_id[-3:]}",
            "selected_action": "보류",
            "response_time_seconds": 1,
        },
    )
    assert premature_final.status_code == 409
    assert premature_final.json()["error"]["code"] == "invalid_practice_transition"

    first_turn = scenario.dialogue_turns[0]
    partial = _example(answer_key, first_turn.turn_id, "partial_check")
    partial_response = client.post(
        turns_endpoint,
        headers=headers,
        json={
            "request_id": f"partial-{scenario_id[-3:]}",
            "turn_id": first_turn.turn_id,
            "user_answer": partial.user_input,
            "response_time_seconds": 1,
        },
    )
    assert partial_response.status_code == 200
    assert partial_response.json()["attempt_no"] == 1
    assert partial_response.json()["evaluation"]["answer_category"] == "partial_check"
    assert partial_response.json()["session"]["current_state"] == partial.expected_next_turn_id

    # partial_check는 평가 데이터에 따라 진행 또는 재시도가 모두 가능하다.
    # 전체 완료·멱등성 검증은 모든 목표 행동을 확인할 수 있도록 새 세션에서 수행한다.
    session = _create_session(client, headers, scenario_id)
    session_id = session["practice_session_id"]
    turns_endpoint = f"/api/practice-sessions/{session_id}/turns"

    timeout = _timeout_example(answer_key, first_turn.turn_id)
    timeout_response = client.post(
        turns_endpoint,
        headers=headers,
        json={
            "request_id": f"provider-timeout-{scenario_id[-3:]}",
            "turn_id": first_turn.turn_id,
            "user_answer": timeout.user_input,
            "response_time_seconds": 1,
        },
    )
    assert timeout_response.status_code == 200
    assert timeout_response.json()["attempt_no"] == 1
    assert timeout_response.json()["evaluation"]["answer_category"] == "needs_review"
    assert timeout_response.json()["evaluation"]["fallback_reason"] == "provider_timeout"
    assert timeout_response.json()["session"]["current_state"] == first_turn.turn_id

    request_ids: list[tuple[str, dict]] = []
    for index, turn in enumerate(scenario.dialogue_turns, start=1):
        appropriate = _example(answer_key, turn.turn_id, "appropriate_check")
        request_id = f"appropriate-{scenario_id[-3:]}-{index:02d}"
        body = {
            "request_id": request_id,
            "turn_id": turn.turn_id,
            "user_answer": appropriate.user_input,
            "response_time_seconds": 1,
        }
        response = client.post(turns_endpoint, headers=headers, json=body)
        assert response.status_code == 200, response.text
        assert response.json()["evaluation"]["answer_category"] == "appropriate_check"
        assert response.json()["evaluation"]["evidence_text"] == appropriate.user_input
        request_ids.append((request_id, body))
        if index == 1:
            assert response.json()["attempt_no"] == 2

    duplicate = client.post(
        turns_endpoint,
        headers=headers,
        json=request_ids[0][1],
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_practice_request"

    action_state = client.get(f"/api/practice-sessions/{session_id}", headers=headers)
    assert action_state.status_code == 200
    assert action_state.json()["current_state"] == "ACTION-SELECTION"
    assert action_state.json()["current_turn"] is None
    assert action_state.json()["confirmed_action_ids"] == [action.action_id for action in scenario.target_actions]

    disallowed = client.post(
        f"/api/practice-sessions/{session_id}/final-action",
        headers=headers,
        json={
            "request_id": f"disallowed-{scenario_id[-3:]}",
            "selected_action": "특약 수정 요구",
            "response_time_seconds": 1,
        },
    )
    assert disallowed.status_code == 409
    assert disallowed.json()["error"]["code"] == "invalid_practice_transition"

    completed = client.post(
        f"/api/practice-sessions/{session_id}/final-action",
        headers=headers,
        json={
            "request_id": f"complete-{scenario_id[-3:]}",
            "selected_action": "보류",
            "response_time_seconds": 1,
        },
    )
    assert completed.status_code == 200, completed.text
    completed_session = completed.json()["session"]
    assert completed_session["status"] == "completed"
    assert completed_session["current_state"] == "DEBRIEF"
    assert completed_session["selected_action"] == "보류"

    first_result = client.get(f"/api/practice-sessions/{session_id}/result", headers=headers)
    second_result = client.get(f"/api/practice-sessions/{session_id}/result", headers=headers)
    assert first_result.status_code == 200
    assert second_result.json() == first_result.json()
    result = first_result.json()["result"]
    assert result["scenario_id"] == scenario_id
    assert result["selected_action"] == "보류"
    assert result["confirmed_action_ids"] == [action.action_id for action in scenario.target_actions]
    assert result["missed_action_ids"] == []
    assert set(result["official_source_ids"]) <= set(answer_key.debrief.official_source_ids)

    after_completion = client.post(
        turns_endpoint,
        headers=headers,
        json={
            "request_id": f"after-complete-{scenario_id[-3:]}",
            "turn_id": "TURN-01",
            "user_answer": "다시 답변하겠습니다.",
            "response_time_seconds": 1,
        },
    )
    assert after_completion.status_code == 409
    assert after_completion.json()["error"]["code"] == "invalid_practice_transition"

    final_again = client.post(
        f"/api/practice-sessions/{session_id}/final-action",
        headers=headers,
        json={
            "request_id": f"final-again-{scenario_id[-3:]}",
            "selected_action": "보류",
            "response_time_seconds": 1,
        },
    )
    assert final_again.status_code == 409
    assert final_again.json()["error"]["code"] == "invalid_practice_transition"

    restored = client.get(f"/api/practice-sessions/{session_id}", headers=headers)
    assert restored.status_code == 200
    assert restored.json() == completed_session
