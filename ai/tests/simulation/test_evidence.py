from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from lease_companion_ai.simulation.evidence import retrieve_action_evidence
from lease_companion_ai.simulation.models import load_practice_assets
from lease_companion_ai.simulation.rules import run_practice_rules


ROOT = Path(__file__).resolve().parents[3]
SCENARIO_ROOT = ROOT / "data" / "sample" / "practice-scenarios"


class _CountingEvidenceService:
    """허용 source를 첫 검색에서 전부 돌려주는 stub. 검색 호출 횟수만 센다."""

    def __init__(self) -> None:
        self.search_count = 0

    def search(self, query, *, top_k: int = 20, top_n: int = 5):
        self.search_count += 1
        hits = [
            SimpleNamespace(
                chunk=SimpleNamespace(
                    text=f"{source_id} 근거 본문",
                    metadata=SimpleNamespace(
                        source_id=source_id,
                        document_title="테스트 공식자료",
                        institution="테스트 기관",
                        source_url=None,
                    ),
                ),
                retrieval_method=None,
            )
            for source_id in query.allowed_source_ids
        ]
        return SimpleNamespace(hits=hits)


def test_allowed_source_ids_found_stops_remaining_rule_searches():
    """허용 source를 다 찾으면 남은 rule 검색을 돌지 않는다.

    복기 진입이 rule 24개 × action 3개 = 72회 동기 RAG 검색으로 지연되던 문제의 회귀 검사.
    """
    fixture_dir = SCENARIO_ROOT / "PRACTICE-DEFERRED-REFUND-001"
    scenario, _ = load_practice_assets(
        fixture_dir / "scenario.json",
        fixture_dir / "answer-key.json",
    )
    rules = run_practice_rules(scenario)
    assert len(rules) > 1, "rule이 1개면 조기 종료를 검증할 수 없다."

    service = _CountingEvidenceService()
    evidence = retrieve_action_evidence(
        scenario, scenario.target_actions[0].action_id, rules, service
    )

    assert len(evidence) > 0
    assert service.search_count == 1
