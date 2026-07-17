"""생성·Guardrail 단계 전후 규칙 엔진 판정 필드의 불변성을 검사한다."""

from __future__ import annotations

from lease_companion_ai.schemas.unified import RuleResult


_IMMUTABLE_FIELDS = ("status", "urgency", "reason")


def changed_rule_fields(before: RuleResult, after: RuleResult) -> tuple[str, ...]:
    return tuple(
        field
        for field in _IMMUTABLE_FIELDS
        if getattr(before, field) != getattr(after, field)
    )
