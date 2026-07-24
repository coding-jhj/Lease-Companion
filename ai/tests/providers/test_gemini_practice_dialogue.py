from pathlib import Path
from types import SimpleNamespace

from lease_companion_ai.providers.gemini_practice_dialogue import (
    GeminiPracticeDialogueProvider,
    build_practice_dialogue_provider,
)
from lease_companion_ai.simulation.dialogue_planner import DialoguePlan
from lease_companion_ai.simulation.dialogue_provider import DialogueGenerationRequest
from lease_companion_ai.simulation.models import load_practice_assets


ROOT = Path(__file__).resolve().parents[3]
SCENARIO_ROOT = ROOT / "data" / "sample" / "practice-scenarios"


class FakeModels:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed=self.parsed, text=None)


class RecordingGateway:
    def __init__(self):
        self.calls = []

    def call(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs["operation"]()


def _request():
    scenario, _ = load_practice_assets(
        SCENARIO_ROOT / "PRACTICE-DEFERRED-REFUND-001" / "scenario.json",
        SCENARIO_ROOT / "PRACTICE-DEFERRED-REFUND-001" / "answer-key.json",
    )
    config = scenario.grounded_roleplay
    return DialogueGenerationRequest(
        prompt_version=config.prompt_version,
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.scenario_version,
        turn_id="TURN-01",
        user_answer="새 세입자가 없으면 언제 반환되나요?",
        evaluation_category="partial_check",
        role="공인중개사",
        approved_facts=(config.approved_facts[1],),
        plan=DialoguePlan(
            question_intent="no_successor_case",
            speech_act="state_missing_fact",
            allowed_fact_ids=("F02",),
            forbidden_fact_ids=("F01", "F03", "F04"),
            role_instruction="공인중개사 입장에서 사용자의 질문에만 답한다.",
            persuasion_instruction="새로운 보장이나 관행을 만들지 않는다.",
        ),
        allowed_entities=("신규 임차인", "보증금", "특약"),
    )


def test_gemini_dialogue_uses_structured_schema_and_four_input_sections():
    models = FakeModels(
        {
            "response_text": "그 경우의 반환 시점은 현재 특약에 따로 적혀 있지 않습니다.",
            "used_fact_ids": ["F02"],
            "claims": [{"fact_id": "F02", "relation": "paraphrase"}],
            "speech_act": "state_missing_fact",
        }
    )
    gateway = RecordingGateway()
    provider = GeminiPracticeDialogueProvider(
        client=SimpleNamespace(models=models),
        gateway=gateway,
    )

    result = provider.generate(_request())

    assert result.used_fact_ids == ("F02",)
    call = models.calls[0]
    assert call["contents"][0].splitlines()[0] == "버전: practice-dialogue-v1"
    payload = call["contents"][1]
    assert '"role"' in payload
    assert '"approved_facts"' in payload
    assert '"dialogue_plan"' in payload
    assert '"current_context"' in payload
    assert "answer_key" not in payload
    assert "hidden_confirmation_signals" not in payload
    assert call["config"].temperature == 0
    assert gateway.calls[0]["task"] == "practice_dialogue_generation"


def test_dialogue_provider_factory_is_enabled_only_for_configured_scenario(monkeypatch):
    deferred, _ = load_practice_assets(
        SCENARIO_ROOT / "PRACTICE-DEFERRED-REFUND-001" / "scenario.json",
        SCENARIO_ROOT / "PRACTICE-DEFERRED-REFUND-001" / "answer-key.json",
    )
    proxy, _ = load_practice_assets(
        SCENARIO_ROOT / "PRACTICE-PROXY-AUTHORITY-001" / "scenario.json",
        SCENARIO_ROOT / "PRACTICE-PROXY-AUTHORITY-001" / "answer-key.json",
    )
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    assert build_practice_dialogue_provider(deferred) is not None
    assert build_practice_dialogue_provider(proxy) is None
    assert build_practice_dialogue_provider(deferred, offline_mode=True) is None
