"""dev/test를 분리해 공식 근거 검색 품질을 실측한다."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from lease_companion_ai.rag.models import RetrievalQuery
from lease_companion_ai.rag.service import EvidenceRetrievalService
from lease_companion_ai.schemas.unified import RuleStatus


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationCase:
    case_id: str
    query: RetrievalQuery
    expected_source_ids: tuple[str, ...]
    allowed_source_ids: tuple[str, ...]


RetrievalFailureReason = Literal[
    "expected_source_not_locally_available",
    "allowlist_filtered",
    "bm25_candidate_miss",
    "outside_top_k",
]


@dataclass(frozen=True, slots=True)
class RetrievalFailureDiagnostic:
    case_id: str
    rule_id: str
    expected_source_id: str
    reason: RetrievalFailureReason


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    split: Literal["dev", "test"]
    measured_at: str
    config_version: str
    top_k: int
    candidate_k: int
    case_count: int
    query_count: int
    top_k_answer_inclusion_count: int
    top_k_answer_inclusion_rate: float
    expected_source_hit_count: int
    expected_source_count: int
    expected_source_recall: float
    locally_available_expected_source_count: int
    locally_available_expected_source_hit_count: int
    locally_available_expected_source_recall: float
    failure_reason_counts: dict[str, int]
    locally_unavailable_expected_source_ids: tuple[str, ...]
    actionable_failure_diagnostics: tuple[RetrievalFailureDiagnostic, ...]
    source_retrieval_frequency: dict[str, int]
    citation_count: int
    complete_citation_count: int
    unofficial_source_exposure_count: int
    provider_fallback_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_retrieval(
    cases: list[RetrievalEvaluationCase],
    service: EvidenceRetrievalService,
    *,
    split: Literal["dev", "test"],
    measured_at: date,
    config_version: str,
    locally_available_source_ids: set[str] | frozenset[str],
    top_k: int = 5,
    candidate_k: int = 20,
) -> RetrievalMetrics:
    if top_k <= 0:
        raise ValueError("top_k는 양수여야 합니다.")
    if not cases:
        raise ValueError("평가 사례가 없습니다.")
    if candidate_k < top_k:
        raise ValueError("candidate_k는 top_k 이상이어야 합니다.")
    if any(not case.allowed_source_ids for case in cases):
        raise ValueError("모든 평가 사례에 R 공식자료 allowlist가 필요합니다.")
    if split == "test" and any(not case.case_id.startswith("TEST-") for case in cases):
        raise ValueError("test split에는 TEST-* 사례만 허용됩니다.")
    if split == "dev" and any(case.case_id.startswith("TEST-") for case in cases):
        raise ValueError("dev split에 TEST-* 사례를 섞을 수 없습니다.")

    inclusion_count = 0
    expected_hit_count = 0
    expected_count = 0
    available_expected_count = 0
    available_expected_hit_count = 0
    failure_counts: Counter[str] = Counter(
        {
            "expected_source_not_locally_available": 0,
            "allowlist_filtered": 0,
            "bm25_candidate_miss": 0,
            "outside_top_k": 0,
        }
    )
    locally_unavailable_source_ids: set[str] = set()
    actionable_failure_diagnostics: list[RetrievalFailureDiagnostic] = []
    frequency: Counter[str] = Counter()
    citation_count = 0
    complete_citation_count = 0
    unofficial_count = 0
    fallback_count = 0
    for case in cases:
        result = service.search(case.query, top_k=candidate_k, top_n=candidate_k)
        fallback_count += int(result.provider_fallback_used)
        candidate_hits = result.hits
        final_hits = candidate_hits[:top_k]
        candidate_source_ids = {
            hit.chunk.metadata.source_id for hit in candidate_hits
        }
        source_ids = {hit.chunk.metadata.source_id for hit in final_hits}
        expected = set(case.expected_source_ids)
        allowed = set(case.allowed_source_ids)
        hits = source_ids & expected
        inclusion_count += int(bool(hits))
        expected_hit_count += len(hits)
        expected_count += len(expected)
        locally_available_expected = expected & locally_available_source_ids
        available_expected_count += len(locally_available_expected)
        available_expected_hit_count += len(hits & locally_available_expected)
        for expected_source_id in sorted(expected - hits):
            if expected_source_id not in locally_available_source_ids:
                reason: RetrievalFailureReason = (
                    "expected_source_not_locally_available"
                )
                locally_unavailable_source_ids.add(expected_source_id)
            elif expected_source_id not in allowed:
                reason = "allowlist_filtered"
            elif expected_source_id not in candidate_source_ids:
                reason = "bm25_candidate_miss"
            else:
                reason = "outside_top_k"
            failure_counts[reason] += 1
            if reason != "expected_source_not_locally_available":
                actionable_failure_diagnostics.append(
                    RetrievalFailureDiagnostic(
                        case_id=case.case_id,
                        rule_id=case.query.rule_id,
                        expected_source_id=expected_source_id,
                        reason=reason,
                    )
                )
        for hit in final_hits:
            metadata = hit.chunk.metadata
            frequency[metadata.source_id] += 1
            citation_count += 1
            complete_citation_count += int(
                bool(
                    metadata.document_title
                    and metadata.institution
                    and metadata.article_or_section
                    and metadata.source_url
                    and metadata.source_sha256
                )
            )
            unofficial_count += int(metadata.source_status != "official_verified")

    query_count = len(cases)
    return RetrievalMetrics(
        split=split,
        measured_at=measured_at.isoformat(),
        config_version=config_version,
        top_k=top_k,
        candidate_k=candidate_k,
        case_count=len({case.case_id for case in cases}),
        query_count=query_count,
        top_k_answer_inclusion_count=inclusion_count,
        top_k_answer_inclusion_rate=inclusion_count / query_count,
        expected_source_hit_count=expected_hit_count,
        expected_source_count=expected_count,
        expected_source_recall=expected_hit_count / expected_count if expected_count else 0.0,
        locally_available_expected_source_count=available_expected_count,
        locally_available_expected_source_hit_count=available_expected_hit_count,
        locally_available_expected_source_recall=(
            available_expected_hit_count / available_expected_count
            if available_expected_count
            else 0.0
        ),
        failure_reason_counts=dict(failure_counts),
        locally_unavailable_expected_source_ids=tuple(
            sorted(locally_unavailable_source_ids)
        ),
        actionable_failure_diagnostics=tuple(actionable_failure_diagnostics),
        source_retrieval_frequency=dict(sorted(frequency.items())),
        citation_count=citation_count,
        complete_citation_count=complete_citation_count,
        unofficial_source_exposure_count=unofficial_count,
        provider_fallback_count=fallback_count,
    )


def load_gold_cases(
    rag_goldset: Path,
    rule_goldset: Path,
    rule_spec: Path,
    rule_evidence_map: Path,
) -> list[RetrievalEvaluationCase]:
    with rule_spec.open(encoding="utf-8", newline="") as handle:
        rule_names = {row["rule_id"]: row["rule_name"] for row in csv.DictReader(handle)}
    rule_records = [
        json.loads(line)
        for line in rule_goldset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    statuses = {
        (record["case_id"], rule["rule_id"]): RuleStatus(rule["status"])
        for record in rule_records
        for rule in record["gold_rules"]
    }
    with rule_evidence_map.open(encoding="utf-8", newline="") as handle:
        allowed_source_ids: dict[str, list[str]] = {}
        for row in csv.DictReader(handle):
            allowed_source_ids.setdefault(row["rule_id"], []).append(row["source_id"])
    cases: list[RetrievalEvaluationCase] = []
    for line in rag_goldset.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        for expected in record["expected_evidence"]:
            rule_id = expected["rule_id"]
            cases.append(
                RetrievalEvaluationCase(
                    case_id=record["case_id"],
                    query=RetrievalQuery(
                        rule_id=rule_id,
                        rule_name=rule_names[rule_id],
                        status=statuses[(record["case_id"], rule_id)],
                    ),
                    expected_source_ids=tuple(expected["expected_source_ids"]),
                    allowed_source_ids=tuple(allowed_source_ids[rule_id]),
                )
            )
    return cases
