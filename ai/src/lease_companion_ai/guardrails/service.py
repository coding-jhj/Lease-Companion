"""사용자 안내를 저장 가능한 안전 출력으로 제한한다."""

from __future__ import annotations

import logging

from lease_companion_ai.generation.models import JudgmentGuidance, RuleGuidance
from lease_companion_ai.guardrails.grounding import (
    grounding_violations,
    judgment_grounding_violations,
)
from lease_companion_ai.guardrails.immutable_rules import changed_rule_fields
from lease_companion_ai.guardrails.prohibited_claims import has_prohibited_claim
from lease_companion_ai.schemas.unified import JudgmentResult, RuleResult

logger = logging.getLogger(__name__)


class GuardrailBlocked(ValueError):
    """차단 코드만 전달하고 생성 본문이나 개인정보는 포함하지 않는다."""

    def __init__(self, rule_id: str, reasons: tuple[str, ...]) -> None:
        self.rule_id = rule_id
        self.reasons = reasons
        super().__init__(f"guardrail blocked {rule_id}: {','.join(reasons)}")


class GuardrailService:
    def enforce(self, rule: RuleResult, guidance: RuleGuidance) -> RuleGuidance:
        signing_texts = tuple(item.text for item in guidance.signing_checklist_items)
        post_action_texts = tuple(item.text for item in guidance.post_contract_action_items)
        texts = (
            guidance.explanation,
            *guidance.questions,
            *(signing_texts or guidance.signing_checklist),
            *(post_action_texts or guidance.post_contract_actions),
        )
        reasons = list(grounding_violations(rule, guidance))
        if has_prohibited_claim(texts):
            reasons.append("prohibited_claim")
        unique_reasons = tuple(dict.fromkeys(reasons))
        if unique_reasons:
            logger.warning(
                "generation_guardrail_blocked",
                extra={"rule_id": rule.rule_id, "reason_codes": unique_reasons},
            )
            raise GuardrailBlocked(rule.rule_id, unique_reasons)
        return guidance

    def enforce_judgment(
        self, judgment: JudgmentResult, guidance: JudgmentGuidance
    ) -> JudgmentGuidance:
        signing_texts = tuple(item.text for item in guidance.signing_checklist_items)
        post_action_texts = tuple(item.text for item in guidance.post_contract_action_items)
        texts = (
            guidance.explanation,
            *guidance.questions,
            *(signing_texts or guidance.signing_checklist),
            *(post_action_texts or guidance.post_contract_actions),
        )
        reasons = list(judgment_grounding_violations(judgment, guidance))
        if has_prohibited_claim(texts):
            reasons.append("prohibited_claim")
        unique_reasons = tuple(dict.fromkeys(reasons))
        if unique_reasons:
            logger.warning(
                "generation_guardrail_blocked",
                extra={
                    "judgment_id": judgment.judgment_id,
                    "reason_codes": unique_reasons,
                },
            )
            raise GuardrailBlocked(judgment.judgment_id, unique_reasons)
        return guidance

    def enforce_rule_immutability(
        self, before: RuleResult, after: RuleResult
    ) -> RuleResult:
        if changed_rule_fields(before, after):
            reasons = ("rule_mutation",)
            logger.warning(
                "generation_guardrail_blocked",
                extra={"rule_id": before.rule_id, "reason_codes": reasons},
            )
            raise GuardrailBlocked(before.rule_id, reasons)
        return after
