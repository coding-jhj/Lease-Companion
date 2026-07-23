"""Gemini structured output용 JSON Schema 정리."""

from __future__ import annotations

from typing import Any


_UNSUPPORTED_KEYS = frozenset({"additionalProperties", "title", "default"})


def clean_gemini_response_schema(node: Any) -> Any:
    """Gemini가 거부하는 Pydantic JSON Schema 키를 재귀적으로 제거한다."""

    if isinstance(node, dict):
        return {
            key: clean_gemini_response_schema(value)
            for key, value in node.items()
            if key not in _UNSUPPORTED_KEYS
        }
    if isinstance(node, list):
        return [clean_gemini_response_schema(item) for item in node]
    return node
