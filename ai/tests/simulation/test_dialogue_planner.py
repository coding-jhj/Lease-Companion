from pathlib import Path

from lease_companion_ai.schemas.simulation import PracticeTurnEvaluation
from lease_companion_ai.simulation.dialogue_planner import plan_grounded_dialogue
from lease_companion_ai.simulation.models import load_practice_assets


ROOT = Path(__file__).resolve().parents[3]
SCENARIO_ROOT = ROOT / "data" / "sample" / "practice-scenarios"


def _assets(scenario_id: str = "PRACTICE-DEFERRED-REFUND-001"):
    return load_practice_assets(
        SCENARIO_ROOT / scenario_id / "scenario.json",
        SCENARIO_ROOT / scenario_id / "answer-key.json",
    )


def _evaluation(turn_id: str, category: str = "partial_check"):
    return PracticeTurnEvaluation(
        turn_id=turn_id,
        answer_category=category,
        confirmed_action_ids=[],
        next_dialogue_state="TURN-02" if turn_id == "TURN-01" else turn_id,
        fallback_reason=None,
        evidence_text="질문",
    )


def test_no_successor_question_discloses_only_missing_information_fact():
    scenario, _ = _assets()

    plan = plan_grounded_dialogue(
        scenario,
        scenario.dialogue_turns[0],
        "새 세입자가 안 들어오면 보증금은 언제 반환되나요?",
        _evaluation("TURN-01"),
    )

    assert plan is not None
    assert plan.question_intent == "no_successor_case"
    assert plan.speech_act == "state_missing_fact"
    assert plan.allowed_fact_ids == ("F02",)


def test_landlord_promise_question_uses_reported_statement():
    scenario, _ = _assets()

    plan = plan_grounded_dialogue(
        scenario,
        scenario.dialogue_turns[1],
        "임대인이 정말 금방 구해진다고 약속했나요?",
        _evaluation("TURN-02"),
    )

    assert plan is not None
    assert plan.question_intent == "verbal_promise"
    assert plan.speech_act == "relay_landlord_claim"
    assert plan.allowed_fact_ids == ("F03", "F04")


def test_clause_change_request_acknowledges_without_disclosing_model_answer():
    scenario, _ = _assets()

    plan = plan_grounded_dialogue(
        scenario,
        scenario.dialogue_turns[1],
        "후임 임차인 조건을 삭제하도록 특약을 고쳐 주세요.",
        _evaluation("TURN-02"),
    )

    assert plan is not None
    assert plan.question_intent == "clause_change_request"
    assert plan.speech_act == "acknowledge_request"
    assert plan.allowed_fact_ids == ()


def test_non_question_does_not_proactively_disclose_facts():
    scenario, _ = _assets()

    plan = plan_grounded_dialogue(
        scenario,
        scenario.dialogue_turns[0],
        "그대로 진행하겠습니다.",
        _evaluation("TURN-01", "avoidance"),
    )

    assert plan is not None
    assert plan.speech_act == "maintain_position"
    assert plan.allowed_fact_ids == ()


def test_other_scenario_keeps_existing_dialogue_path():
    scenario, _ = _assets("PRACTICE-PROXY-AUTHORITY-001")

    plan = plan_grounded_dialogue(
        scenario,
        scenario.dialogue_turns[0],
        "위임장이 있나요?",
        _evaluation("TURN-01"),
    )

    assert plan is None


def test_dialogue_plan_has_no_emotion_field():
    scenario, _ = _assets()

    plan = plan_grounded_dialogue(
        scenario,
        scenario.dialogue_turns[0],
        "이 특약은 무슨 뜻인가요?",
        _evaluation("TURN-01"),
    )

    assert plan is not None
    assert "emotion" not in type(plan).model_fields
