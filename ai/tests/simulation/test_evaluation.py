from __future__ import annotations

import importlib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.rag.models import RagChunk, RagSourceMetadata, RetrievalHit
from lease_companion_ai.rag.service import EvidenceRetrievalService
from lease_companion_ai.schemas.simulation import PracticeTurnEvaluation, PracticeTurnInput
from lease_companion_ai.schemas.unified import OfficialSource, RuleStatus


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = (
    ROOT
    / "data"
    / "sample"
    / "practice-scenarios"
    / "PRACTICE-BROKER-PRESSURE-001"
)
DEFERRED_FIXTURE_DIR = (
    ROOT
    / "data"
    / "sample"
    / "practice-scenarios"
    / "PRACTICE-DEFERRED-REFUND-001"
)


def _modules():
    try:
        return {
            name: importlib.import_module(f"lease_companion_ai.simulation.{name}")
            for name in ("models", "rules", "provider", "service", "evidence", "debrief")
        }
    except ModuleNotFoundError:
        pytest.fail("3단계 simulation 평가기 모듈이 아직 없습니다.")


def _assets():
    modules = _modules()
    return modules["models"].load_practice_assets(
        FIXTURE_DIR / "scenario.json",
        FIXTURE_DIR / "answer-key.json",
    )


class StubProvider:
    model_name = "stub-practice-v1"

    def __init__(self, output=None, error: Exception | None = None) -> None:
        self.output = output
        self.error = error
        self.calls: list[Any] = []

    def classify(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.output


def _turn_input(turn_id: str, answer: str) -> PracticeTurnInput:
    return PracticeTurnInput(
        session_id="practice-session-001",
        turn_id=turn_id,
        user_answer=answer,
        response_time_seconds=3.5,
    )


def test_approved_assets_load_and_rules_link_to_target_actions():
    modules = _modules()
    scenario, answer_key = _assets()

    results = modules["rules"].run_practice_rules(scenario)
    links = modules["rules"].link_actions_to_rules(scenario, results)
    by_id = {result.rule_id: result for result in results}

    assert answer_key.scenario_id == scenario.scenario_id
    assert len(results) == 24
    assert by_id["R03"].status == "확인 필요"
    assert by_id["R06"].status == "불일치"
    assert by_id["R08"].status == "불명확"
    assert by_id["R10"].status == "미기재"
    assert [result.rule_id for result in links["PA04"]] == ["R06"]
    assert [result.rule_id for result in links["PA03"]] == ["R08", "R10"]


@pytest.mark.parametrize(
    "turn_id,answer,category,confirmed,next_state",
    [
        (
            "TURN-01",
            "지금 결정하지 않고 필요한 서류를 확인한 뒤 답하겠습니다.",
            "appropriate_check",
            ["PA01"],
            "TURN-02",
        ),
        ("TURN-01", "조금 더 생각해 볼게요.", "ambiguous_answer", [], "TURN-01"),
        ("TURN-01", "네, 바로 진행할게요.", "avoidance", [], "TURN-01"),
        ("TURN-02", "등기사항증명서를 다시 보여 주세요.", "partial_check", [], "TURN-02"),
    ],
)
def test_provider_categories_follow_the_approved_turn_contract(
    turn_id, answer, category, confirmed, next_state
):
    modules = _modules()
    scenario, answer_key = _assets()
    provider = StubProvider(
        PracticeTurnEvaluation(
            turn_id=turn_id,
            answer_category=category,
            confirmed_action_ids=confirmed,
            next_dialogue_state=next_state,
        )
    )
    evaluator = modules["service"].PracticeEvaluationService(
        scenario, answer_key, provider
    )

    result = evaluator.evaluate(_turn_input(turn_id, answer))

    assert result.answer_category == category
    assert result.confirmed_action_ids == confirmed
    assert provider.calls[0].prompt_version == "practice-evaluation-v1"


@pytest.mark.parametrize(
    "answer,expected_response",
    [
        (
            "후임 임차인이 안 구해지면 어떻게 되나요?",
            "그 경우의 반환 시점은 현재 특약에 따로 적혀 있지 않습니다.",
        ),
        (
            "계약 종료일에 바로 돌려받을 수 있나요?",
            "현재 특약은 새 임차인의 입주와 보증금 수령 후 반환하는 내용입니다.",
        ),
        (
            "특약 3번은 무슨 뜻인가요?",
            "현재 특약은 새 임차인의 입주와 보증금 수령 후 반환하는 내용입니다.",
        ),
        (
            "이 특약 조건을 삭제해 주세요.",
            "특약 수정 요청은 임대인분께 전달해 보겠습니다.",
        ),
    ],
)
def test_same_turn_uses_question_specific_counterparty_response(answer, expected_response):
    modules = _modules()
    scenario, answer_key = modules["models"].load_practice_assets(
        DEFERRED_FIXTURE_DIR / "scenario.json",
        DEFERRED_FIXTURE_DIR / "answer-key.json",
    )
    provider = StubProvider(
        PracticeTurnEvaluation(
            turn_id="TURN-01",
            answer_category="partial_check",
            confirmed_action_ids=[],
            next_dialogue_state="TURN-01",
        )
    )
    service = modules["service"].PracticeSimulationService(scenario, answer_key, provider)
    occurred_at = datetime.now(timezone.utc)
    session = service.start_session("practice-session-variant", 1, occurred_at)

    step = service.submit(
        session,
        PracticeTurnInput(
            session_id=session.session_id,
            turn_id="TURN-01",
            user_answer=answer,
            response_time_seconds=3.5,
        ),
        occurred_at=occurred_at,
    )

    assert step.dialogue_response == expected_response


def test_timeout_input_is_no_response_without_calling_provider():
    modules = _modules()
    scenario, answer_key = _assets()
    provider = StubProvider(error=AssertionError("provider를 호출하면 안 됩니다."))
    evaluator = modules["service"].PracticeEvaluationService(
        scenario, answer_key, provider
    )

    result = evaluator.evaluate(
        PracticeTurnInput(
            session_id="practice-session-001",
            turn_id="TURN-01",
            timed_out=True,
            response_time_seconds=10,
        )
    )

    assert result.answer_category == "no_response"
    assert result.next_dialogue_state == "TURN-01"
    assert provider.calls == []


@pytest.mark.parametrize(
    "error,reason",
    [
        (TimeoutError(), "provider_timeout"),
        (ProviderError("provider failed"), "provider_error"),
    ],
)
def test_provider_failures_return_needs_review_fallback(error, reason):
    modules = _modules()
    scenario, answer_key = _assets()
    evaluator = modules["service"].PracticeEvaluationService(
        scenario, answer_key, StubProvider(error=error)
    )

    result = evaluator.evaluate(_turn_input("TURN-02", "최신 등기를 확인하겠습니다."))

    assert result.answer_category == "needs_review"
    assert result.fallback_reason == reason
    assert result.next_dialogue_state == "TURN-02"


def test_invalid_provider_state_is_rejected_as_response_validation_fallback():
    modules = _modules()
    scenario, answer_key = _assets()
    invalid = PracticeTurnEvaluation(
        turn_id="TURN-02",
        answer_category="appropriate_check",
        confirmed_action_ids=["PA02"],
        next_dialogue_state="TURN-99",
    )
    evaluator = modules["service"].PracticeEvaluationService(
        scenario, answer_key, StubProvider(invalid)
    )

    result = evaluator.evaluate(_turn_input("TURN-02", "최신 등기를 확인하겠습니다."))

    assert result.answer_category == "needs_review"
    assert result.fallback_reason == "response_validation_failed"


def test_provider_cannot_change_rule_status_or_urgency():
    modules = _modules()
    scenario, answer_key = _assets()

    class MutatingProvider(StubProvider):
        def classify(self, request):
            object.__setattr__(request.rule_states[0], "status", RuleStatus.CLEAR)
            return PracticeTurnEvaluation(
                turn_id=request.turn_id,
                answer_category="appropriate_check",
                confirmed_action_ids=[request.goal_action_id],
                next_dialogue_state=request.success_next_state,
            )

    evaluator = modules["service"].PracticeEvaluationService(
        scenario, answer_key, MutatingProvider()
    )
    before = [(item.rule_id, item.status, item.urgency) for item in evaluator.rule_results]

    result = evaluator.evaluate(_turn_input("TURN-01", "확인 후 결정하겠습니다."))

    after = [(item.rule_id, item.status, item.urgency) for item in evaluator.rule_results]
    assert result.answer_category == "needs_review"
    assert result.fallback_reason == "rule_mutation"
    assert after == before


class IgnoringAllowlistRetriever:
    def __init__(self, hits):
        self.hits = hits

    def search(self, query, *, top_k=20):
        return list(self.hits)


def _hit(source_id: str, rank: int) -> RetrievalHit:
    metadata = RagSourceMetadata(
        source_id=source_id,
        document_title=f"{source_id} 자료",
        institution="공식기관",
        document_type="official_guidance",
        article_or_section="확인 항목",
        source_url=f"https://example.go.kr/{source_id.lower()}",
        collected_date=date(2026, 7, 20),
        source_sha256=f"{rank:064x}",
        usage_terms="공공누리",
    )
    return RetrievalHit(
        chunk=RagChunk(
            chunk_id=f"{source_id}:{rank:064x}",
            metadata=metadata,
            section="확인 항목",
            ordinal=0,
            text="계약 전에 관련 자료를 확인합니다.",
        ),
        score=1.0,
        rank=rank,
        retrieval_method="hybrid",
    )


def test_practice_rag_returns_only_sources_approved_for_the_target_action():
    modules = _modules()
    scenario, _ = _assets()
    rules = modules["rules"].run_practice_rules(scenario)
    links = modules["rules"].link_actions_to_rules(scenario, rules)
    rag = EvidenceRetrievalService(
        IgnoringAllowlistRetriever(
            [_hit("SRC-STD-LEASE", 1), _hit("SRC-NOT-APPROVED", 2)]
        ),
        rule_source_ids={},
        rule_search_contexts={},
        judgment_source_ids={},
        judgment_search_contexts={},
    )

    evidence = modules["evidence"].retrieve_action_evidence(
        scenario, "PA04", links["PA04"], rag
    )

    assert [item.source_id for item in evidence] == ["SRC-STD-LEASE"]


def test_debrief_rejects_unapproved_evidence_and_prohibited_claims():
    modules = _modules()
    scenario, answer_key = _assets()
    evaluations = [
        PracticeTurnEvaluation(
            turn_id="TURN-01",
            answer_category="appropriate_check",
            confirmed_action_ids=["PA01"],
            next_dialogue_state="TURN-02",
        )
    ]
    unapproved = OfficialSource(
        source_id="SRC-NOT-APPROVED",
        title="비공식 자료",
        institution="알 수 없음",
    )

    with pytest.raises(modules["debrief"].PracticeGuardrailBlocked, match="unapproved_source"):
        modules["debrief"].build_practice_result(
            "practice-session-001",
            scenario,
            answer_key,
            evaluations,
            {"PA01": [unapproved]},
        )

    unsafe_debrief = answer_key.debrief.model_copy(
        update={"next_actions": ("이 계약은 안전합니다.",)}
    )
    unsafe_key = answer_key.model_copy(update={"debrief": unsafe_debrief})
    with pytest.raises(modules["debrief"].PracticeGuardrailBlocked, match="prohibited_claim"):
        modules["debrief"].build_practice_result(
            "practice-session-001",
            scenario,
            unsafe_key,
            evaluations,
            {},
        )


def test_safe_debrief_contains_actions_missed_signals_and_approved_evidence():
    modules = _modules()
    scenario, answer_key = _assets()
    evaluations = [
        PracticeTurnEvaluation(
            turn_id="TURN-01",
            answer_category="appropriate_check",
            confirmed_action_ids=["PA01"],
            next_dialogue_state="TURN-02",
        )
    ]
    source = OfficialSource(
        source_id="SRC-STD-LEASE",
        title="표준 주택임대차계약서",
        institution="국토교통부",
    )

    result = modules["debrief"].build_practice_result(
        "practice-session-001",
        scenario,
        answer_key,
        evaluations,
        {"PA04": [source]},
    )

    assert result.confirmed_action_ids == ["PA01"]
    assert result.missed_action_ids == ["PA02", "PA03", "PA04"]
    assert result.missed_signals
    assert result.official_source_ids == ["SRC-STD-LEASE"]


def test_practice_judgment_state_accepts_every_canonical_judgment_id():
    """연습 평가 요청의 judgment_id는 canonical 판정 축 전체를 받아야 한다.

    정규식을 J01~J12로 하드코딩해 두면 J13이 연결된 시나리오가 생기는 순간
    ValidationError로 평가 자체가 막힌다. 판정 축이 늘어날 때마다 이 파일을
    고쳐야 하는 구조를 막기 위해 canonical 상수에서 전부 확인한다.
    """
    from lease_companion_ai.schemas.unified import JUDGMENT_IDS, Urgency

    from lease_companion_ai.simulation.provider import PracticeJudgmentState

    for judgment_id in JUDGMENT_IDS:
        state = PracticeJudgmentState(
            judgment_id=judgment_id,
            status=RuleStatus.CHECK_NEEDED,
            urgency=Urgency.IMMEDIATE,
        )
        assert state.judgment_id == judgment_id
