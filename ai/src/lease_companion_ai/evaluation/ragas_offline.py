"""RAGAS ID 지표로 일반·특약 RAG의 로컬 BM25 결과를 평가한다."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from importlib.metadata import version
from pathlib import Path

from ragas.dataset_schema import SingleTurnSample
from ragas.metrics import IDBasedContextPrecision, IDBasedContextRecall

from lease_companion_ai.evaluation.retrieval import load_gold_cases
from lease_companion_ai.rag.clause_service import (
    build_clause_retrieval_query,
    build_special_clause_retrieval_service,
    load_special_clause_chunks,
)
from lease_companion_ai.rag.service import (
    build_evidence_service,
    load_local_official_chunks,
)
from lease_companion_ai.schemas.unified import RuleStatus
from lease_companion_ai.special_clauses import match_special_clauses


@dataclass(frozen=True, slots=True)
class RagasIdCase:
    case_id: str
    retrieved_context_ids: tuple[str, ...]
    reference_context_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RagasIdCaseScore:
    case_id: str
    retrieved_context_ids: tuple[str, ...]
    reference_context_ids: tuple[str, ...]
    context_precision: float
    context_recall: float


@dataclass(frozen=True, slots=True)
class RagasIdMetricSummary:
    scope: str
    top_k: int
    evaluated_case_count: int
    excluded_no_reference_case_count: int
    macro_context_precision: float
    macro_context_recall: float
    case_scores: tuple[RagasIdCaseScore, ...]


@dataclass(frozen=True, slots=True)
class RagasOfflineMetrics:
    measured_at: str
    split: str
    config_version: str
    ragas_version: str
    general_rag_sources: RagasIdMetricSummary
    special_clause_sources: RagasIdMetricSummary
    special_clause_sections: RagasIdMetricSummary
    external_provider_call_count: int
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def score_ragas_id_cases(
    cases: list[RagasIdCase], *, scope: str, top_k: int
) -> RagasIdMetricSummary:
    """정답 ID가 있는 사례만 RAGAS macro 평균에 포함한다."""
    if not cases:
        raise ValueError("RAGAS 평가 사례가 없습니다.")
    if top_k <= 0:
        raise ValueError("top_k는 양수여야 합니다.")

    precision_metric = IDBasedContextPrecision()
    recall_metric = IDBasedContextRecall()
    scores: list[RagasIdCaseScore] = []
    excluded = 0
    for case in cases:
        if not case.reference_context_ids:
            excluded += 1
            continue
        sample = SingleTurnSample(
            retrieved_context_ids=list(case.retrieved_context_ids),
            reference_context_ids=list(case.reference_context_ids),
        )
        precision = float(precision_metric.single_turn_score(sample))
        recall = float(recall_metric.single_turn_score(sample))
        if math.isnan(precision) or math.isnan(recall):
            raise ValueError(f"RAGAS ID 점수를 계산할 수 없습니다: {case.case_id}")
        scores.append(
            RagasIdCaseScore(
                case_id=case.case_id,
                retrieved_context_ids=case.retrieved_context_ids,
                reference_context_ids=case.reference_context_ids,
                context_precision=precision,
                context_recall=recall,
            )
        )
    if not scores:
        raise ValueError("정답 ID가 있는 RAGAS 평가 사례가 없습니다.")
    return RagasIdMetricSummary(
        scope=scope,
        top_k=top_k,
        evaluated_case_count=len(scores),
        excluded_no_reference_case_count=excluded,
        macro_context_precision=sum(item.context_precision for item in scores)
        / len(scores),
        macro_context_recall=sum(item.context_recall for item in scores) / len(scores),
        case_scores=tuple(scores),
    )


def _general_rag_cases(root: Path, *, top_k: int) -> list[RagasIdCase]:
    chunks = load_local_official_chunks(root)
    service = build_evidence_service(chunks)
    gold_cases = load_gold_cases(
        root / "data/evaluation/end-to-end/final_testset_rag.jsonl",
        root / "data/evaluation/end-to-end/final_testset_rule.jsonl",
        root / "data/rules/rule_spec.csv",
        root / "data/rules/rule_evidence_map.csv",
    )
    cases = []
    for case in gold_cases:
        result = service.search(case.query, top_k=20, top_n=20)
        cases.append(
            RagasIdCase(
                case_id=f"{case.case_id}:{case.query.rule_id}",
                retrieved_context_ids=tuple(
                    hit.chunk.metadata.source_id for hit in result.hits[:top_k]
                ),
                reference_context_ids=case.expected_source_ids,
            )
        )
    return cases


def _special_clause_rag_cases(
    root: Path, *, top_k: int
) -> tuple[list[RagasIdCase], list[RagasIdCase]]:
    records = _read_jsonl(
        root / "data/evaluation/special-clauses/retrieval_test.jsonl"
    )
    service = build_special_clause_retrieval_service(
        chunks=load_special_clause_chunks(root)
    )
    source_cases: list[RagasIdCase] = []
    section_cases: list[RagasIdCase] = []
    for record in records:
        case_id = str(record["case_id"])
        expected_sources = tuple(str(value) for value in record["expected_source_ids"])
        expected_sections = tuple(str(value) for value in record["expected_sections"])
        if not bool(record["expect_evidence"]):
            source_cases.append(RagasIdCase(case_id, (), ()))
            section_cases.append(RagasIdCase(case_id, (), ()))
            continue

        candidate = match_special_clauses([str(record["text"])])[0]
        query = build_clause_retrieval_query(
            candidate,
            status=RuleStatus.CHECK_NEEDED,
            related_result_contexts=tuple(
                [*candidate.related_rule_ids, *candidate.related_judgment_ids]
            ),
        )
        hits = service.search(query).hits[:top_k]
        source_cases.append(
            RagasIdCase(
                case_id=case_id,
                retrieved_context_ids=tuple(
                    hit.chunk.metadata.source_id for hit in hits
                ),
                reference_context_ids=expected_sources,
            )
        )
        section_cases.append(
            RagasIdCase(
                case_id=case_id,
                retrieved_context_ids=tuple(
                    f"{hit.chunk.metadata.source_id}::{hit.chunk.section}"
                    for hit in hits
                ),
                reference_context_ids=tuple(
                    f"{source_id}::{section}"
                    for source_id, section in zip(
                        expected_sources, expected_sections, strict=True
                    )
                ),
            )
        )
    return source_cases, section_cases


def evaluate_ragas_offline(
    root: Path, *, measured_at: date
) -> RagasOfflineMetrics:
    general_top_k = 5
    special_top_k = 3
    special_sources, special_sections = _special_clause_rag_cases(
        root, top_k=special_top_k
    )
    return RagasOfflineMetrics(
        measured_at=measured_at.isoformat(),
        split="test",
        config_version="ragas-id-offline-bm25-v1",
        ragas_version=version("ragas"),
        general_rag_sources=score_ragas_id_cases(
            _general_rag_cases(root, top_k=general_top_k),
            scope="general_rag_source_top5",
            top_k=general_top_k,
        ),
        special_clause_sources=score_ragas_id_cases(
            special_sources,
            scope="special_clause_source_top3",
            top_k=special_top_k,
        ),
        special_clause_sections=score_ragas_id_cases(
            special_sections,
            scope="special_clause_source_section_top3",
            top_k=special_top_k,
        ),
        external_provider_call_count=0,
        limitations=(
            "RAGAS ID 기반 지표만 측정했으며 LLM 기반 지표는 실제 API 호출 제외로 측정하지 않았습니다.",
            "일반 RAG는 로컬 BM25 source Top-5, 특약 RAG는 source·section Top-3 기준입니다.",
            "정답 context ID가 없는 근거 없음 사례는 macro 평균에서 제외하고 별도 집계했습니다.",
            "잠긴 합성 test 기준선이며 실제 계약서나 독립 사람 검토 성능이 아닙니다.",
        ),
    )
