from __future__ import annotations

import importlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[3]
SCENARIO_PATH = (
    ROOT
    / "data"
    / "sample"
    / "practice-scenarios"
    / "PRACTICE-BROKER-PRESSURE-001"
    / "scenario.json"
)


def _models():
    try:
        return importlib.import_module("lease_companion_ai.schemas.simulation")
    except ModuleNotFoundError:
        pytest.fail("simulation canonical schema module이 아직 없습니다.")


def _scenario_payload() -> dict:
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


def test_approved_scenario_fixture_passes_and_references_are_consistent():
    simulation = _models()

    scenario = simulation.ScenarioDefinition.model_validate(_scenario_payload())

    assert scenario.scenario_id == "PRACTICE-BROKER-PRESSURE-001"
    assert scenario.dialogue_turns[-1].next_turn_id == "ACTION-SELECTION"
    assert simulation.ScenarioDefinition.model_validate_json(scenario.model_dump_json()) == scenario


def test_scenario_id_supports_an_approved_catalog_instead_of_one_hardcoded_id():
    simulation = _models()
    payload = _scenario_payload()
    payload["scenario_id"] = "PRACTICE-LANDLORD-PROXY-001"

    scenario = simulation.ScenarioDefinition.model_validate(payload)

    assert scenario.scenario_id == "PRACTICE-LANDLORD-PROXY-001"


@pytest.mark.parametrize(
    "mutate,error",
    [
        (lambda payload: payload["dialogue_turns"].append(payload["dialogue_turns"][0]), "중복 turn_id"),
        (lambda payload: payload["dialogue_turns"][0].update(next_turn_id="TURN-99"), "next_turn_id"),
        (lambda payload: payload["dialogue_turns"][0].update(goal_action_id="PA99"), "goal_action_id"),
        (lambda payload: payload.update(terminal_state_id="UNKNOWN"), "terminal_state_id"),
    ],
)
def test_scenario_rejects_broken_state_and_action_references(mutate, error):
    simulation = _models()
    payload = _scenario_payload()
    mutate(payload)

    with pytest.raises(ValidationError, match=error):
        simulation.ScenarioDefinition.model_validate(payload)


def test_media_manifest_requires_unique_states_and_both_viewports():
    simulation = _models()
    payload = {
        "scenario_id": "PRACTICE-BROKER-PRESSURE-001",
        "scenario_version": "1.0.0",
        "media_version": "1.0.0",
        "clips": [
            {
                "state": "waiting_soft",
                "poster_url": "/media/waiting-soft.webp",
                "subtitle": "답변을 기다리고 있습니다.",
                "loop": True,
                "desktop_video_url": "/media/waiting-soft-desktop.mp4",
                "mobile_video_url": "/media/waiting-soft-mobile.mp4",
            }
        ],
    }
    manifest = simulation.ScenarioMediaManifest.model_validate(payload)
    assert manifest.clips[0].loop is True

    duplicate = deepcopy(payload)
    duplicate["clips"].append(deepcopy(duplicate["clips"][0]))
    with pytest.raises(ValidationError, match="중복 media state"):
        simulation.ScenarioMediaManifest.model_validate(duplicate)

    missing_mobile = deepcopy(payload)
    missing_mobile["clips"][0]["mobile_video_url"] = None
    with pytest.raises(ValidationError, match="desktop.*mobile"):
        simulation.ScenarioMediaManifest.model_validate(missing_mobile)


def test_practice_session_completion_fields_are_consistent():
    simulation = _models()
    started_at = datetime(2026, 7, 20, tzinfo=timezone.utc)
    active = simulation.PracticeSessionState(
        session_id="practice-session-001",
        user_id=1,
        scenario_id="PRACTICE-BROKER-PRESSURE-001",
        scenario_version="1.0.0",
        current_state="TURN-01",
        started_at=started_at,
        status="active",
    )
    assert active.completed_at is None

    with pytest.raises(ValidationError, match="completed_at"):
        simulation.PracticeSessionState(
            session_id="practice-session-001",
            user_id=1,
            scenario_id="PRACTICE-BROKER-PRESSURE-001",
            scenario_version="1.0.0",
            current_state="DEBRIEF",
            started_at=started_at,
            status="completed",
        )


def test_turn_input_requires_an_answer_or_selected_action():
    simulation = _models()
    valid = simulation.PracticeTurnInput(
        session_id="practice-session-001",
        turn_id="TURN-01",
        user_answer="  최신 등기를 확인하겠습니다.  ",
        selected_action=None,
        response_time_seconds=4.2,
    )
    assert valid.user_answer == "최신 등기를 확인하겠습니다."

    with pytest.raises(ValidationError, match="답변 또는 행동"):
        simulation.PracticeTurnInput(
            session_id="practice-session-001",
            turn_id="TURN-01",
            user_answer=" ",
            selected_action=None,
            response_time_seconds=4.2,
        )


def test_turn_input_represents_timeout_and_action_selection_explicitly():
    simulation = _models()
    timeout = simulation.PracticeTurnInput(
        session_id="practice-session-001",
        turn_id="TURN-01",
        user_answer=None,
        selected_action=None,
        timed_out=True,
        response_time_seconds=10,
    )
    action = simulation.PracticeTurnInput(
        session_id="practice-session-001",
        turn_id="ACTION-SELECTION",
        user_answer=None,
        selected_action="보류",
        timed_out=False,
        response_time_seconds=2,
    )

    assert timeout.timed_out is True
    assert action.selected_action == "보류"


def test_turn_evaluation_enforces_fallback_and_unique_actions():
    simulation = _models()
    fallback = simulation.PracticeTurnEvaluation(
        turn_id="TURN-02",
        answer_category="needs_review",
        confirmed_action_ids=[],
        next_dialogue_state="TURN-02",
        fallback_reason="provider_timeout",
    )
    assert fallback.fallback_reason == "provider_timeout"

    with pytest.raises(ValidationError, match="fallback_reason"):
        simulation.PracticeTurnEvaluation(
            turn_id="TURN-02",
            answer_category="appropriate_check",
            confirmed_action_ids=["PA02"],
            next_dialogue_state="TURN-03",
            fallback_reason="provider_timeout",
        )

    with pytest.raises(ValidationError, match="중복 confirmed_action_ids"):
        simulation.PracticeTurnEvaluation(
            turn_id="TURN-02",
            answer_category="appropriate_check",
            confirmed_action_ids=["PA02", "PA02"],
            next_dialogue_state="TURN-03",
            fallback_reason=None,
        )

    with pytest.raises(ValidationError, match="appropriate_check"):
        simulation.PracticeTurnEvaluation(
            turn_id="TURN-02",
            answer_category="appropriate_check",
            confirmed_action_ids=[],
            next_dialogue_state="TURN-03",
            fallback_reason=None,
        )


def test_practice_result_keeps_confirmed_and_missed_actions_disjoint():
    simulation = _models()
    valid = simulation.PracticeResult(
        session_id="practice-session-001",
        scenario_id="PRACTICE-BROKER-PRESSURE-001",
        scenario_version="1.0.0",
        confirmed_action_ids=["PA01"],
        missed_action_ids=["PA02"],
        recommended_phrases=["최신 등기사항증명서를 확인하겠습니다."],
        next_actions=["계약 직전 최신 등기를 확인한다."],
        official_source_ids=["SRC-MOLIT-CHECKLIST"],
    )
    assert valid.confirmed_action_ids == ["PA01"]

    with pytest.raises(ValidationError, match="동시에"):
        simulation.PracticeResult(
            session_id="practice-session-001",
            scenario_id="PRACTICE-BROKER-PRESSURE-001",
            scenario_version="1.0.0",
            confirmed_action_ids=["PA01"],
            missed_action_ids=["PA01"],
            recommended_phrases=[],
            next_actions=[],
            official_source_ids=[],
        )


def test_simulation_models_are_public_exports():
    schemas = importlib.import_module("lease_companion_ai.schemas")
    for name in (
        "ScenarioDefinition",
        "ScenarioMediaManifest",
        "PracticeSessionState",
        "PracticeTurnInput",
        "PracticeTurnEvaluation",
        "PracticeResult",
    ):
        assert hasattr(schemas, name), f"공개 export 누락: {name}"


def test_simulation_json_schemas_are_generated_from_canonical_models():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from generate_unified_schemas import MODELS, build_schema

    expected = {
        "scenario-definition",
        "scenario-media-manifest",
        "practice-session-state",
        "practice-turn-input",
        "practice-turn-evaluation",
        "practice-result",
    }
    assert expected <= set(MODELS)
    for name in expected:
        path = ROOT / "data" / "schemas" / "generated" / f"{name}.schema.json"
        assert path.exists(), f"생성 스키마 누락: {path}"
        assert json.loads(path.read_text(encoding="utf-8")) == build_schema(name, MODELS[name])
