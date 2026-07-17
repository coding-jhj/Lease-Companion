import logging

import pytest

from lease_companion_ai.generation.models import GenerationMethod, RuleGuidance
from lease_companion_ai.guardrails.immutable_rules import changed_rule_fields
from lease_companion_ai.guardrails.service import GuardrailBlocked, GuardrailService
from lease_companion_ai.schemas.unified import (
    OfficialSource,
    ResultType,
    RuleResult,
    RuleStatus,
    Urgency,
)


def _rule(*, with_evidence: bool = True) -> RuleResult:
    return RuleResult(
        rule_id="R01",
        rule_name="소유자 일치 확인",
        result_type=ResultType.JUDGMENT,
        triggers_actions=True,
        status=RuleStatus.CHECK_NEEDED,
        urgency=Urgency.BEFORE_CONTRACT,
        reason="임대인: 홍길동 확인 필요",
        question="등기 소유자를 확인했습니까?",
        recommended_actions=["등기사항증명서를 확인하십시오."],
        evidence_sources=(
            [
                OfficialSource(
                    source_id="SRC-HTA-LAW",
                    title="법령",
                    institution="국가법령정보센터",
                )
            ]
            if with_evidence
            else []
        ),
        limitations="제공 문서 범위",
    )


def _guidance(**updates: object) -> RuleGuidance:
    values: dict[str, object] = {
        "rule_id": "R01",
        "explanation": "공식 근거에 따라 소유자 정보를 확인하십시오.",
        "questions": ("등기 소유자를 확인했습니까?",),
        "signing_checklist": ("등기사항증명서를 확인하십시오.",),
        "source_ids": ("SRC-HTA-LAW",),
        "generation_method": GenerationMethod.PROVIDER,
        "provider_model": "fake-generation-v1",
    }
    values.update(updates)
    return RuleGuidance.model_validate(values)


@pytest.mark.parametrize(
    "claim",
    [
        "이 계약은 안전합니다.",
        "이 거래는 위험해요.",
        "안전한 계약입니다.",
        "전세사기가 아닙니다.",
        "전세사기 가능성이 없습니다.",
        "이 조항은 위법입니다.",
        "계약해도 됩니다.",
        "계약하지 마십시오.",
    ],
)
def test_blocks_prohibited_certainty_variants(claim: str):
    with pytest.raises(GuardrailBlocked) as exc_info:
        GuardrailService().enforce(_rule(), _guidance(explanation=claim))

    assert exc_info.value.reasons == ("prohibited_claim",)


def test_blocks_ungrounded_explanation_and_action():
    guidance = _guidance(
        explanation="이 행동을 바로 완료하십시오.",
        signing_checklist=("즉시 서명하십시오.",),
        source_ids=(),
    )

    with pytest.raises(GuardrailBlocked) as exc_info:
        GuardrailService().enforce(_rule(with_evidence=False), guidance)

    assert exc_info.value.reasons == (
        "ungrounded_action",
        "ungrounded_explanation",
    )


def test_blocks_unknown_source_id():
    with pytest.raises(GuardrailBlocked) as exc_info:
        GuardrailService().enforce(
            _rule(), _guidance(source_ids=("SRC-NOT-PROVIDED",))
        )

    assert exc_info.value.reasons == ("invalid_source_id",)


def test_block_log_contains_only_safe_rule_and_reason_codes(caplog):
    caplog.set_level(logging.WARNING)

    with pytest.raises(GuardrailBlocked):
        GuardrailService().enforce(
            _rule(), _guidance(explanation="이 계약은 안전합니다.")
        )

    record = caplog.records[-1]
    assert record.getMessage() == "generation_guardrail_blocked"
    assert record.rule_id == "R01"
    assert record.reason_codes == ("prohibited_claim",)
    assert "홍길동" not in record.getMessage()


def test_detects_rule_status_urgency_and_reason_mutation():
    before = _rule()
    after = before.model_copy(
        update={
            "status": RuleStatus.MATCH,
            "urgency": Urgency.REFERENCE,
            "reason": "변경된 이유",
        }
    )

    assert changed_rule_fields(before, after) == ("status", "urgency", "reason")
    with pytest.raises(GuardrailBlocked) as exc_info:
        GuardrailService().enforce_rule_immutability(before, after)
    assert exc_info.value.reasons == ("rule_mutation",)
