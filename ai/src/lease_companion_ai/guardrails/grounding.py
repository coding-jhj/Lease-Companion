"""생성 안내가 연결된 공식 근거의 범위를 벗어나지 않는지 검사한다."""

from __future__ import annotations

from lease_companion_ai.generation.models import RuleGuidance
from lease_companion_ai.schemas.unified import RuleResult


def grounding_violations(
    rule: RuleResult, guidance: RuleGuidance
) -> tuple[str, ...]:
    allowed = {source.source_id for source in rule.evidence_sources}
    violations: list[str] = []
    if not set(guidance.source_ids).issubset(allowed):
        violations.append("invalid_source_id")
    if not guidance.source_ids:
        if guidance.signing_checklist or guidance.post_contract_actions:
            violations.append("ungrounded_action")
        if "공식 근거 확인이 필요" not in guidance.explanation:
            violations.append("ungrounded_explanation")
    return tuple(violations)
