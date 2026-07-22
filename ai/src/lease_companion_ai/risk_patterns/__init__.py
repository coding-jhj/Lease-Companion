"""기존 판정을 피해 유형 관점의 표시 결과로 묶는다."""

from .service import attach_damage_patterns, build_damage_patterns
from .reference_cases import load_verified_reference_cases, search_reference_cases

__all__ = [
    "attach_damage_patterns",
    "build_damage_patterns",
    "load_verified_reference_cases",
    "search_reference_cases",
]
