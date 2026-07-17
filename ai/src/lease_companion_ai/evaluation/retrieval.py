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


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    split: Literal["dev", "test"]
    measured_at: str
    config_version: str
    top_k: int
    case_count: int
    query_count: int
    top_k_answer_inclusion_count: int
    top_k_answer_inclusion_rate: float
    expected_source_hit_count: int
    expected_source_count: int
    expected_source_recall: float
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
    top_k: int = 5,
) -> RetrievalMetrics:
    if top_k <= 0:
        raise ValueError("top_k는 양수여야 합니다.")
    if not cases:
        raise ValueError("평가 사례가 없습니다.")
    if split == "test" and any(not case.case_id.startswith("TEST-") for case in cases):
        raise ValueError("test split에는 TEST-* 사례만 허용됩니다.")
    if split == "dev" and any(case.case_id.startswith("TEST-") for case in cases):
        raise ValueError("dev split에 TEST-* 사례를 섞을 수 없습니다.")

    inclusion_count = 0
    expected_hit_count = 0
    expected_count = 0
    frequency: Counter[str] = Counter()
    citation_count = 0
    complete_citation_count = 0
    unofficial_count = 0
    fallback_count = 0
    for case in cases:
        result = service.search(case.query, top_k=20, top_n=top_k)
        fallback_count += int(result.provider_fallback_used)
        source_ids = {hit.chunk.metadata.source_id for hit in result.hits}
        expected = set(case.expected_source_ids)
        hits = source_ids & expected
        inclusion_count += int(bool(hits))
        expected_hit_count += len(hits)
        expected_count += len(expected)
        for hit in result.hits:
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
        case_count=len({case.case_id for case in cases}),
        query_count=query_count,
        top_k_answer_inclusion_count=inclusion_count,
        top_k_answer_inclusion_rate=inclusion_count / query_count,
        expected_source_hit_count=expected_hit_count,
        expected_source_count=expected_count,
        expected_source_recall=expected_hit_count / expected_count if expected_count else 0.0,
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
                )
            )
    return cases
