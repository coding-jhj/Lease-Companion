from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lease_companion_ai.providers.gemini_practice import (
    FakePracticeProvider,
    GeminiPracticeProvider,
    build_practice_provider,
)
from lease_companion_ai.schemas.simulation import PracticeTurnInput
from lease_companion_ai.simulation.models import load_practice_assets
from lease_companion_ai.simulation.service import PracticeEvaluationService


ROOT = Path(__file__).resolve().parents[3]
PRACTICE_ROOT = ROOT / "data" / "sample" / "practice-scenarios"
SCENARIO_IDS = (
    "PRACTICE-DEFERRED-REFUND-001",
    "PRACTICE-THIRD-PARTY-PAYMENT-001",
    "PRACTICE-PROXY-AUTHORITY-001",
)


def _assets(scenario_id: str = SCENARIO_IDS[0]):
    directory = PRACTICE_ROOT / scenario_id
    return load_practice_assets(
        directory / "scenario.json",
        directory / "answer-key.json",
    )


class FakeModels:
    def __init__(self, *, parsed=None, text=None, error: Exception | None = None):
        self.parsed = parsed
        self.text = text
        self.error = error
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(parsed=self.parsed, text=self.text)


def _turn_input(turn_id: str, answer: str) -> PracticeTurnInput:
    return PracticeTurnInput(
        session_id="practice-session-001",
        turn_id=turn_id,
        user_answer=answer,
        response_time_seconds=2,
    )


def _appropriate_payload(turn_id: str, action_id: str, next_state: str) -> dict:
    return {
        "turn_id": turn_id,
        "answer_category": "appropriate_check",
        "confirmed_action_ids": [action_id],
        "next_dialogue_state": next_state,
        "fallback_reason": None,
        "evidence_text": "사용자 답변 원문",
        "verbal_reliance": "rejected",
    }


def test_gemini_practice_uses_fixed_model_schema_prompt_and_read_only_rj():
    scenario, answer_key = _assets()
    models = FakeModels(parsed=_appropriate_payload("TURN-01", "PA01", "TURN-02"))
    provider = GeminiPracticeProvider(client=SimpleNamespace(models=models))
    service = PracticeEvaluationService(scenario, answer_key, provider)

    result = service.evaluate(
        _turn_input("TURN-01", "후임 임차인 입주 조건인지 확인하겠습니다.")
    )

    assert result.answer_category == "appropriate_check"
    assert result.evidence_text == "후임 임차인 입주 조건인지 확인하겠습니다."
    call = models.calls[0]
    assert call["model"] == "gemini-3.5-flash"
    config = call["config"]
    assert config.response_mime_type == "application/json"
    assert config.temperature == 0
    assert config.thinking_config.thinking_budget == 0
    assert "additionalProperties" not in json.dumps(config.response_schema)
    assert call["contents"][0].splitlines()[0] == "버전: practice-evaluation-v1"
    payload = json.loads(call["contents"][1])
    assert payload["scenario_id"] == scenario.scenario_id
    assert payload["goal_action_id"] == "PA01"
    assert len(payload["rule_states"]) == 24
    assert payload["judgment_states"][0]["judgment_id"] == "J10"


def test_gemini_practice_accepts_json_text_fallback():
    scenario, answer_key = _assets()
    models = FakeModels(
        text=json.dumps(
            _appropriate_payload("TURN-01", "PA01", "TURN-02"),
            ensure_ascii=False,
        )
    )
    service = PracticeEvaluationService(
        scenario,
        answer_key,
        GeminiPracticeProvider(client=SimpleNamespace(models=models)),
    )

    result = service.evaluate(_turn_input("TURN-01", "반환 조건을 확인하겠습니다."))

    assert result.answer_category == "appropriate_check"


@pytest.mark.parametrize("parsed,text", [({"invalid": True}, None), (None, "{"), (None, None)])
def test_gemini_practice_rejects_invalid_or_empty_structured_response(parsed, text):
    scenario, answer_key = _assets()
    models = FakeModels(parsed=parsed, text=text)
    provider = GeminiPracticeProvider(client=SimpleNamespace(models=models))
    service = PracticeEvaluationService(scenario, answer_key, provider)

    result = service.evaluate(_turn_input("TURN-01", "반환 조건을 확인하겠습니다."))

    assert result.answer_category == "needs_review"
    assert result.fallback_reason == "response_validation_failed"
    assert result.next_dialogue_state == "TURN-01"


def test_gemini_practice_distinguishes_timeout_and_sanitizes_sdk_error():
    scenario, answer_key = _assets()
    timeout_service = PracticeEvaluationService(
        scenario,
        answer_key,
        GeminiPracticeProvider(
            client=SimpleNamespace(models=FakeModels(error=TimeoutError()))
        ),
    )
    error_service = PracticeEvaluationService(
        scenario,
        answer_key,
        GeminiPracticeProvider(
            client=SimpleNamespace(
                models=FakeModels(error=RuntimeError("secret user answer"))
            )
        ),
    )

    timeout = timeout_service.evaluate(
        _turn_input("TURN-01", "반환 조건을 확인하겠습니다.")
    )
    error = error_service.evaluate(
        _turn_input("TURN-01", "반환 조건을 확인하겠습니다.")
    )

    assert timeout.fallback_reason == "provider_timeout"
    assert error.fallback_reason == "provider_error"


def test_gemini_practice_maps_quota_error_to_safe_provider_fallback():
    scenario, answer_key = _assets()
    service = PracticeEvaluationService(
        scenario,
        answer_key,
        GeminiPracticeProvider(
            client=SimpleNamespace(
                models=FakeModels(
                    error=RuntimeError("429 RESOURCE_EXHAUSTED secret quota detail")
                )
            )
        ),
    )

    result = service.evaluate(_turn_input("TURN-01", "확인하겠습니다."))

    assert result.answer_category == "needs_review"
    assert result.fallback_reason == "provider_error"
    assert result.evidence_text == "확인하겠습니다."


def test_gemini_practice_rejects_unapproved_action_and_state():
    scenario, answer_key = _assets()
    invalid = _appropriate_payload("TURN-01", "PA99", "TURN-99")
    service = PracticeEvaluationService(
        scenario,
        answer_key,
        GeminiPracticeProvider(
            client=SimpleNamespace(models=FakeModels(parsed=invalid))
        ),
    )

    result = service.evaluate(_turn_input("TURN-01", "확인하겠습니다."))

    assert result.answer_category == "needs_review"
    assert result.fallback_reason == "response_validation_failed"


def test_gemini_practice_does_not_require_sdk_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    scenario, answer_key = _assets()
    service = PracticeEvaluationService(
        scenario, answer_key, GeminiPracticeProvider()
    )

    result = service.evaluate(_turn_input("TURN-01", "확인하겠습니다."))

    assert result.answer_category == "needs_review"
    assert result.fallback_reason == "provider_error"


def test_provider_factory_prefers_key_then_offline_fake_then_none(monkeypatch):
    scenario, answer_key = _assets()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    keyed = build_practice_provider(scenario, answer_key, offline_mode=True)
    assert isinstance(keyed, GeminiPracticeProvider)

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-key")
    google_keyed = build_practice_provider(scenario, answer_key, offline_mode=True)
    assert isinstance(google_keyed, GeminiPracticeProvider)

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    offline = build_practice_provider(scenario, answer_key, offline_mode=True)
    missing = build_practice_provider(scenario, answer_key, offline_mode=False)
    assert isinstance(offline, FakePracticeProvider)
    assert missing is None


def test_offline_fake_does_not_guess_unapproved_free_form_answer(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    scenario, answer_key = _assets()
    provider = build_practice_provider(scenario, answer_key, offline_mode=True)
    assert isinstance(provider, FakePracticeProvider)
    service = PracticeEvaluationService(scenario, answer_key, provider)

    result = service.evaluate(
        _turn_input("TURN-01", "정답표에 없는 새로운 자유 답변입니다.")
    )

    assert result.answer_category == "needs_review"
    assert result.fallback_reason == "fake_no_matching_example"
    assert result.next_dialogue_state == "TURN-01"


OFFLINE_FREE_FORM_EXAMPLES = (
    (
        "PRACTICE-DEFERRED-REFUND-001",
        "TURN-01",
        "다음 세입자가 안 들어오면 계약이 끝나도 보증금을 못 돌려받는 조건인지 확인할게요.",
        "PA01",
        "TURN-02",
    ),
    (
        "PRACTICE-DEFERRED-REFUND-001",
        "TURN-02",
        "새 임차인 입주 조건은 삭제하고 계약 종료일에 반환하도록 특약을 고쳐 주세요.",
        "PA02",
        "TURN-03",
    ),
    (
        "PRACTICE-DEFERRED-REFUND-001",
        "TURN-03",
        "반환 특약이 수정된 것을 확인하기 전에는 서명하지 않고 계약을 보류할게요.",
        "PA03",
        "ACTION-SELECTION",
    ),
    (
        "PRACTICE-THIRD-PARTY-PAYMENT-001",
        "TURN-01",
        "계좌 명의가 소유자인 임대인이 아니라 중개사인 이유를 확인할게요.",
        "PA01",
        "TURN-02",
    ),
    (
        "PRACTICE-THIRD-PARTY-PAYMENT-001",
        "TURN-02",
        "중개사와 임대인의 관계와 돈을 대신 받을 권한 서류를 보여 주세요.",
        "PA02",
        "TURN-03",
    ),
    (
        "PRACTICE-THIRD-PARTY-PAYMENT-001",
        "TURN-03",
        "입금 명의와 수령 권한을 확인할 때까지 가계약금은 송금하지 않겠습니다.",
        "PA03",
        "ACTION-SELECTION",
    ),
    (
        "PRACTICE-PROXY-AUTHORITY-001",
        "TURN-01",
        "등기상 소유자와 지금 나온 대리인이 어떤 관계인지 확인하겠습니다.",
        "PA01",
        "TURN-02",
    ),
    (
        "PRACTICE-PROXY-AUTHORITY-001",
        "TURN-02",
        "위임장과 인감증명서에 계약 체결과 계약금 수령 권한까지 있는지 확인할게요.",
        "PA02",
        "TURN-03",
    ),
    (
        "PRACTICE-PROXY-AUTHORITY-001",
        "TURN-03",
        "대리권을 확인하기 전에는 계약서에 서명하지 않고 계약금도 송금하지 않겠습니다.",
        "PA03",
        "ACTION-SELECTION",
    ),
)


@pytest.mark.parametrize(
    "scenario_id,turn_id,answer,action_id,next_state",
    OFFLINE_FREE_FORM_EXAMPLES,
)
def test_offline_fake_accepts_natural_answers_with_required_intent(
    monkeypatch, scenario_id, turn_id, answer, action_id, next_state
):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    scenario, answer_key = _assets(scenario_id)
    provider = build_practice_provider(scenario, answer_key, offline_mode=True)
    assert isinstance(provider, FakePracticeProvider)
    service = PracticeEvaluationService(scenario, answer_key, provider)

    result = service.evaluate(_turn_input(turn_id, answer))

    assert result.answer_category == "appropriate_check"
    assert result.confirmed_action_ids == [action_id]
    assert result.next_dialogue_state == next_state
    assert result.fallback_reason is None


@pytest.mark.parametrize(
    "scenario_id,turn_id,answer",
    (
        (
            "PRACTICE-DEFERRED-REFUND-001",
            "TURN-02",
            "새 임차인 입주 조건은 그대로 두고 특약 문구만 수정한 뒤 진행하겠습니다.",
        ),
        (
            "PRACTICE-THIRD-PARTY-PAYMENT-001",
            "TURN-03",
            "입금 명의와 수령 권한은 나중에 확인하고 가계약금을 먼저 송금하겠습니다.",
        ),
        (
            "PRACTICE-PROXY-AUTHORITY-001",
            "TURN-03",
            "대리권은 나중에 확인하고 일단 계약서에 서명한 뒤 계약금을 보내겠습니다.",
        ),
    ),
)
def test_offline_fake_does_not_accept_conflicting_free_form_answer(
    monkeypatch, scenario_id, turn_id, answer
):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    scenario, answer_key = _assets(scenario_id)
    provider = build_practice_provider(scenario, answer_key, offline_mode=True)
    assert isinstance(provider, FakePracticeProvider)
    service = PracticeEvaluationService(scenario, answer_key, provider)

    result = service.evaluate(_turn_input(turn_id, answer))

    assert result.answer_category == "needs_review"
    assert result.confirmed_action_ids == []
    assert result.next_dialogue_state == turn_id


FAKE_EXAMPLES = []
for _scenario_id in SCENARIO_IDS:
    _scenario, _answer_key = _assets(_scenario_id)
    for _example in _answer_key.evaluation_examples:
        FAKE_EXAMPLES.append((_scenario, _answer_key, _example))


@pytest.mark.parametrize(
    "scenario,answer_key,example",
    FAKE_EXAMPLES,
    ids=[
        f"{scenario.scenario_id}:{example.example_id}"
        for scenario, _, example in FAKE_EXAMPLES
    ],
)
def test_offline_fake_provider_covers_all_three_answer_keys(
    monkeypatch, scenario, answer_key, example
):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    provider = build_practice_provider(scenario, answer_key, offline_mode=True)
    assert isinstance(provider, FakePracticeProvider)
    service = PracticeEvaluationService(scenario, answer_key, provider)
    timed_out = example.expected_status_id == "no_response"
    turn_input = PracticeTurnInput(
        session_id="practice-session-001",
        turn_id=example.turn_id,
        user_answer=None if timed_out else example.user_input,
        timed_out=timed_out,
        response_time_seconds=example.input_context.elapsed_seconds or 0,
    )

    result = service.evaluate(turn_input)

    assert result.answer_category == example.expected_status_id
    assert result.confirmed_action_ids == list(example.expected_confirmed_action_ids)
    assert result.next_dialogue_state == example.expected_next_turn_id
