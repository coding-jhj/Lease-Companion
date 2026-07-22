"""명시적 승인 환경에서만 실행하는 합성 계약 연습 Gemini smoke test."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lease_companion_ai.providers.gemini_practice import GeminiPracticeProvider
from lease_companion_ai.schemas.simulation import PracticeTurnInput
from lease_companion_ai.simulation.models import load_practice_assets
from lease_companion_ai.simulation.service import PracticeEvaluationService


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_GEMINI_PRACTICE_SMOKE") != "1"
    or not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
    reason=(
        "RUN_GEMINI_PRACTICE_SMOKE=1과 승인된 Gemini API 키가 있을 때만 "
        "호출합니다."
    ),
)


def test_deferred_refund_gemini_practice_smoke():
    directory = Path(
        "data/sample/practice-scenarios/PRACTICE-DEFERRED-REFUND-001"
    )
    scenario, answer_key = load_practice_assets(
        directory / "scenario.json", directory / "answer-key.json"
    )
    service = PracticeEvaluationService(
        scenario, answer_key, GeminiPracticeProvider()
    )

    result = service.evaluate(
        PracticeTurnInput(
            session_id="practice-smoke-001",
            turn_id="TURN-01",
            user_answer=(
                "보증금 반환이 신규 임차인의 입주에 달린 조건인지 확인하겠습니다."
            ),
            response_time_seconds=0,
        )
    )

    assert result.answer_category == "appropriate_check"
    assert result.confirmed_action_ids == ["PA01"]
    assert result.next_dialogue_state == "TURN-02"
