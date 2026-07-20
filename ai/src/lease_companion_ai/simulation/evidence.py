"""연습 목표 행동에 연결된 승인 공식 근거 검색."""

from __future__ import annotations

from collections.abc import Sequence

from lease_companion_ai.rag.models import RetrievalQuery
from lease_companion_ai.rag.service import EvidenceRetrievalService
from lease_companion_ai.schemas.minimum_mvp import RuleResult
from lease_companion_ai.schemas.simulation import ScenarioDefinition
from lease_companion_ai.schemas.unified import OfficialSource, RuleStatus


def retrieve_action_evidence(
    scenario: ScenarioDefinition,
    action_id: str,
    rule_results: Sequence[RuleResult],
    evidence_service: EvidenceRetrievalService,
) -> tuple[OfficialSource, ...]:
    """시나리오 action에 승인된 source ID만 RAG 결과로 반환한다."""

    action = next(
        (item for item in scenario.target_actions if item.action_id == action_id),
        None,
    )
    if action is None:
        raise ValueError("시나리오에 없는 action_id입니다.")
    signals = {
        item.signal_id: item for item in scenario.hidden_confirmation_signals
    }
    allowed_source_ids = tuple(
        dict.fromkeys(
            source_id
            for signal_id in action.linked_signal_ids
            for source_id in signals[signal_id].official_source_ids
        )
    )
    if not allowed_source_ids:
        return ()

    evidence: list[OfficialSource] = []
    seen: set[str] = set()
    allowed = set(allowed_source_ids)
    for rule in rule_results:
        search = evidence_service.search(
            RetrievalQuery(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                status=RuleStatus(rule.status),
                allowed_source_ids=allowed_source_ids,
                evidence_search_context="연습 목표 행동의 공식 확인 근거",
            )
        )
        for hit in search.hits:
            metadata = hit.chunk.metadata
            if metadata.source_id not in allowed or metadata.source_id in seen:
                continue
            seen.add(metadata.source_id)
            evidence.append(
                OfficialSource(
                    source_id=metadata.source_id,
                    title=metadata.document_title,
                    institution=metadata.institution,
                    summary=hit.chunk.text,
                    source_url=metadata.source_url,
                    retrieval_method=hit.retrieval_method,
                )
            )
    return tuple(evidence)
