from pathlib import Path

import pytest

from lease_companion_ai.simulation.dialogue_guardrail import (
    DialogueGuardrailViolation,
    validate_grounded_dialogue,
)
from lease_companion_ai.simulation.dialogue_planner import DialoguePlan
from lease_companion_ai.simulation.dialogue_provider import (
    DialogueClaim,
    DialogueGenerationRequest,
    DialogueGenerationResult,
)
from lease_companion_ai.simulation.models import load_practice_assets


ROOT = Path(__file__).resolve().parents[3]
SCENARIO_ROOT = ROOT / "data" / "sample" / "practice-scenarios"


def _request() -> DialogueGenerationRequest:
    scenario, _ = load_practice_assets(
        SCENARIO_ROOT / "PRACTICE-DEFERRED-REFUND-001" / "scenario.json",
        SCENARIO_ROOT / "PRACTICE-DEFERRED-REFUND-001" / "answer-key.json",
    )
    facts = tuple(
        fact
        for fact in scenario.grounded_roleplay.approved_facts
        if fact.fact_id == "F02"
    )
    return DialogueGenerationRequest(
        prompt_version="practice-dialogue-v1",
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.scenario_version,
        turn_id="TURN-01",
        user_answer="새 세입자가 안 들어오면 언제 반환되나요?",
        evaluation_category="partial_check",
        role="공인중개사",
        approved_facts=facts,
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


def _result(text: str, *, fact_id: str = "F02", speech_act: str = "state_missing_fact"):
    return DialogueGenerationResult(
        response_text=text,
        used_fact_ids=[fact_id] if fact_id else [],
        claims=[DialogueClaim(fact_id=fact_id, relation="paraphrase")]
        if fact_id
        else [],
        speech_act=speech_act,
    )


def test_guardrail_accepts_grounded_short_response():
    result = _result("그 경우의 반환 시점은 현재 특약에 따로 적혀 있지 않습니다.")

    assert validate_grounded_dialogue(_request(), result) == result


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (_result("현재 특약에 적혀 있지 않습니다.", fact_id="F99"), "unapproved_fact"),
        (_result("현재 특약에 적혀 있지 않습니다.", speech_act="answer_fact"), "speech_act_mismatch"),
        (_result("첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다."), "too_many_sentences"),
        (_result("가" * 101), "too_long"),
        (_result("30일 안에 보증금을 반환합니다."), "unapproved_number"),
        (_result("김철수 임대인이 보증금을 반환합니다."), "unapproved_entity"),
        (_result("이 계약은 법적으로 적법합니다."), "prohibited_claim"),
        (_result("특약 수정을 요구하세요."), "model_answer_leak"),
        (_result("좋은 질문입니다. 현재 특약에는 적혀 있지 않습니다."), "model_answer_leak"),
    ],
)
def test_guardrail_rejects_invalid_dialogue(result, code):
    with pytest.raises(DialogueGuardrailViolation) as exc:
        validate_grounded_dialogue(_request(), result)

    assert exc.value.code == code


def test_reported_statement_requires_source_attribution():
    request = _request().model_copy(
        update={
            "approved_facts": (
                _request().model_copy().approved_facts[0].model_copy(
                    update={
                        "fact_id": "F03",
                        "canonical_text": "임대인은 새 임차인이 금방 구해질 것이라고 구두로 말했다.",
                        "claim_kind": "reported_statement",
                    }
                ),
            ),
            "plan": _request().plan.model_copy(
                update={
                    "speech_act": "relay_landlord_claim",
                    "allowed_fact_ids": ("F03",),
                }
            ),
        }
    )
    result = _result(
        "새 임차인은 금방 구해집니다.",
        fact_id="F03",
        speech_act="relay_landlord_claim",
    )

    with pytest.raises(DialogueGuardrailViolation) as exc:
        validate_grounded_dialogue(request, result)

    assert exc.value.code == "missing_attribution"
