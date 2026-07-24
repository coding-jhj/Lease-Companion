"""Grounded roleplay 최종 대사의 결정적 사실·역할 검증."""

from __future__ import annotations

import re

from lease_companion_ai.guardrails.prohibited_claims import has_prohibited_claim
from lease_companion_ai.simulation.dialogue_provider import (
    DialogueGenerationRequest,
    DialogueGenerationResult,
)


class DialogueGuardrailViolation(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


_MODEL_ANSWER_PATTERNS = (
    "요구하세요",
    "확인하세요",
    "보류하세요",
    "중단하세요",
    "수정해 달라고",
    "좋은 질문",
    "정확히 짚",
)
_SENTENCE_END = re.compile(r"[.!?。！？]")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_KOREAN_PERSON = re.compile(r"([가-힣]{2,4})\s*(?:임대인|씨|님)")


def _fail(code: str) -> None:
    raise DialogueGuardrailViolation(code)


def validate_grounded_dialogue(
    request: DialogueGenerationRequest,
    result: DialogueGenerationResult,
) -> DialogueGenerationResult:
    """승인 fact의 바꿔 말하기만 최종 대사로 허용한다."""

    if result.speech_act != request.plan.speech_act:
        _fail("speech_act_mismatch")
    allowed_fact_ids = set(request.plan.allowed_fact_ids)
    used_fact_ids = set(result.used_fact_ids)
    claim_fact_ids = {claim.fact_id for claim in result.claims}
    if not used_fact_ids <= allowed_fact_ids or claim_fact_ids != used_fact_ids:
        _fail("unapproved_fact")

    text = result.response_text.strip()
    if len(text) > 100:
        _fail("too_long")
    if len(_SENTENCE_END.findall(text)) > 2:
        _fail("too_many_sentences")
    if has_prohibited_claim((text,)) or any(
        term in text
        for term in (
            "법적으로 문제없",
            "법적으로 적법",
            "법적으로 유효",
            "반드시 돌려받",
            "계약해도 괜찮",
        )
    ):
        _fail("prohibited_claim")
    if any(pattern in text for pattern in _MODEL_ANSWER_PATTERNS):
        _fail("model_answer_leak")

    approved_text = " ".join(
        fact.canonical_text
        for fact in request.approved_facts
        if fact.fact_id in used_fact_ids
    )
    approved_numbers = set(_NUMBER.findall(approved_text))
    if not set(_NUMBER.findall(text)) <= approved_numbers:
        _fail("unapproved_number")

    allowed_entities = set(request.allowed_entities)
    for match in _KOREAN_PERSON.finditer(text):
        if match.group(1) not in allowed_entities:
            _fail("unapproved_entity")

    facts_by_id = {fact.fact_id: fact for fact in request.approved_facts}
    uses_reported_statement = any(
        facts_by_id[fact_id].claim_kind == "reported_statement"
        for fact_id in used_fact_ids
        if fact_id in facts_by_id
    )
    if uses_reported_statement and not (
        "임대인" in text and any(marker in text for marker in ("말씀", "말했", "구두"))
    ):
        _fail("missing_attribution")
    return result
