"""승인 사실만 공개하는 결정적 계약 연습 대화 계획."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from lease_companion_ai.schemas.simulation import (
    DialogueIntent,
    DialogueTurn,
    PracticeTurnEvaluation,
    ScenarioDefinition,
    SpeechAct,
)


class DialoguePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question_intent: DialogueIntent
    speech_act: SpeechAct
    allowed_fact_ids: tuple[str, ...] = ()
    forbidden_fact_ids: tuple[str, ...] = ()
    role_instruction: str
    persuasion_instruction: str


_INTENT_PRIORITY: tuple[DialogueIntent, ...] = (
    "clause_change_request",
    "contract_hold",
    "no_successor_case",
    "verbal_promise",
    "clause_meaning",
    "return_timing",
    "contract_fact",
    "unrelated",
    "unknown",
)


def _normalize(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _detect_intent(
    scenario: ScenarioDefinition,
    user_answer: str,
) -> DialogueIntent:
    config = scenario.grounded_roleplay
    if config is None:
        return "unknown"
    normalized = _normalize(user_answer)
    matches = {
        intent
        for intent, keywords in config.intent_keywords.items()
        if any(_normalize(keyword) in normalized for keyword in keywords)
    }
    return next((intent for intent in _INTENT_PRIORITY if intent in matches), "unknown")


def _is_question(value: str) -> bool:
    normalized = value.strip()
    return (
        "?" in normalized
        or normalized.endswith(("나요", "가요", "까요", "인가요", "건가요", "습니까"))
    )


def plan_grounded_dialogue(
    scenario: ScenarioDefinition,
    turn: DialogueTurn,
    user_answer: str,
    evaluation: PracticeTurnEvaluation,
) -> DialoguePlan | None:
    """현재 발화에 허용할 사실과 발화 행위를 Python에서 고정한다."""

    config = scenario.grounded_roleplay
    if config is None:
        return None

    intent = _detect_intent(scenario, user_answer)
    questioning = _is_question(user_answer)
    if intent == "clause_change_request":
        speech_act: SpeechAct = "acknowledge_request"
    elif intent == "contract_hold":
        speech_act = "respond_to_hold"
    elif not questioning:
        speech_act = (
            "maintain_position"
            if evaluation.answer_category == "avoidance"
            else "clarify_user_intent"
        )
    elif intent == "no_successor_case":
        speech_act = "state_missing_fact"
    elif intent == "verbal_promise":
        speech_act = "relay_landlord_claim"
    elif intent == "unrelated":
        speech_act = "decline_unrelated"
    elif intent == "unknown":
        speech_act = "clarify_user_intent"
    else:
        speech_act = "answer_fact"

    facts = (
        tuple(
            fact.fact_id
            for fact in config.approved_facts
            if fact.disclosure == "on_request" and intent in fact.allowed_intents
        )
        if questioning and speech_act in {
            "answer_fact",
            "state_missing_fact",
            "relay_landlord_claim",
        }
        else ()
    )
    known_fact_ids = tuple(fact.fact_id for fact in config.approved_facts)
    return DialoguePlan(
        question_intent=intent,
        speech_act=speech_act,
        allowed_fact_ids=facts,
        forbidden_fact_ids=tuple(
            fact_id for fact_id in known_fact_ids if fact_id not in facts
        ),
        role_instruction="공인중개사 입장에서 사용자의 질문에만 답한다.",
        persuasion_instruction=(
            "현재 특약을 유지하려는 입장은 표현할 수 있으나 새로운 보장이나 "
            "관행을 만들지 않는다."
        ),
    )
