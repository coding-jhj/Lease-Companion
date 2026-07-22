"""잠긴 특약 평가셋으로 외부 provider 없는 결정론적 기준선을 측정한다."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from lease_companion_ai.classification.service import ClassificationService
from lease_companion_ai.generation.service import GenerationService
from lease_companion_ai.guardrails.grounding import special_clause_grounding_violations
from lease_companion_ai.pipelines.classified_analysis import analyze_special_clause_flow
from lease_companion_ai.rag.clause_service import (
    SpecialClauseRetrievalService,
    build_clause_retrieval_query,
    build_special_clause_retrieval_service,
)
from lease_companion_ai.rag.service import EvidenceSearchResult
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    ContractContext,
    ContractStage,
    ContractType,
    InputSnapshot,
    RuleStatus,
    SpecialClauseReview,
)
from lease_companion_ai.special_clauses import match_special_clauses


@dataclass(frozen=True, slots=True)
class CatalogTypeMetrics:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float


@dataclass(frozen=True, slots=True)
class SpecialClauseOfflineMetrics:
    catalog_case_count: int
    catalog_exact_match_count: int
    catalog_exact_match_rate: float
    normal_negative_case_count: int
    normal_negative_false_positive_count: int
    normal_negative_false_positive_rate: float
    per_catalog: dict[str, CatalogTypeMetrics]
    retrieval_case_count: int
    expected_source_count: int
    source_top3_hit_count: int
    source_top3_recall: float
    expected_section_count: int
    section_top3_hit_count: int
    section_top3_recall: float
    empty_evidence_case_count: int
    empty_evidence_pass_count: int
    unofficial_source_exposure_count: int
    generation_case_count: int
    generation_output_count: int
    generation_schema_valid_rate: float
    grounding_violation_count: int
    prohibited_claim_count: int
    no_evidence_generation_count: int
    no_evidence_question_only_count: int
    end_to_end_fixture_count: int
    end_to_end_review_match_count: int
    end_to_end_evidence_match_count: int
    end_to_end_guidance_coverage_count: int
    j10_demo_case_count: int
    j10_demo_distinct_query_count: int
    j10_demo_distinct_section_set_count: int
    j10_demo_distinct_revision_request_count: int
    external_provider_call_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _safe_rate(numerator: int, denominator: int, *, empty: float = 0.0) -> float:
    return numerator / denominator if denominator else empty


def _catalog_metrics(root: Path) -> tuple[
    int, int, int, int, dict[str, CatalogTypeMetrics]
]:
    cases = _read_jsonl(
        root / "data/evaluation/special-clauses/catalog_test.jsonl"
    )
    catalog_ids = sorted({case["target_catalog_id"] for case in cases})
    counts: dict[str, Counter[str]] = {
        catalog_id: Counter() for catalog_id in catalog_ids
    }
    exact = 0
    normal_count = 0
    normal_false_positive = 0
    for case in cases:
        actual = set(match_special_clauses([case["text"]])[0].catalog_ids)
        expected = set(case["expected_catalog_ids"])
        exact += int(actual == expected)
        if case["category"] == "normal_negative":
            normal_count += 1
            normal_false_positive += int(bool(actual))
        for catalog_id in catalog_ids:
            counts[catalog_id]["tp"] += int(catalog_id in expected and catalog_id in actual)
            counts[catalog_id]["fp"] += int(catalog_id not in expected and catalog_id in actual)
            counts[catalog_id]["fn"] += int(catalog_id in expected and catalog_id not in actual)
    per_catalog = {}
    for catalog_id, value in counts.items():
        tp, fp, fn = value["tp"], value["fp"], value["fn"]
        per_catalog[catalog_id] = CatalogTypeMetrics(
            true_positive=tp,
            false_positive=fp,
            false_negative=fn,
            precision=_safe_rate(tp, tp + fp, empty=1.0),
            recall=_safe_rate(tp, tp + fn, empty=1.0),
        )
    return len(cases), exact, normal_count, normal_false_positive, per_catalog


def _counter_hits(expected: list[str], actual: list[str]) -> int:
    return sum((Counter(expected) & Counter(actual)).values())


def _retrieval_metrics(root: Path) -> tuple[int, int, int, int, int, int, int, int]:
    cases = _read_jsonl(
        root / "data/evaluation/special-clauses/retrieval_test.jsonl"
    )
    service = build_special_clause_retrieval_service()
    expected_source_count = source_hits = 0
    expected_section_count = section_hits = 0
    empty_count = empty_pass = unofficial = 0
    for case in cases:
        candidate = match_special_clauses([case["text"]])[0]
        if not case["expect_evidence"]:
            empty_count += 1
            empty_pass += int(not candidate.catalog_ids)
            continue
        query = build_clause_retrieval_query(
            candidate,
            status=RuleStatus.CHECK_NEEDED,
            related_result_contexts=tuple(
                [*candidate.related_rule_ids, *candidate.related_judgment_ids]
            ),
        )
        result = service.search(query)
        actual_sources = [hit.chunk.metadata.source_id for hit in result.hits]
        actual_sections = [hit.chunk.section for hit in result.hits]
        expected_sources = list(case["expected_source_ids"])
        expected_sections = list(case["expected_sections"])
        expected_source_count += len(expected_sources)
        source_hits += _counter_hits(expected_sources, actual_sources)
        expected_section_count += len(expected_sections)
        section_hits += _counter_hits(expected_sections, actual_sections)
        allowed_sources = {item.source_id for item in query.allowed_source_sections}
        unofficial += sum(source_id not in allowed_sources for source_id in actual_sources)
    return (
        len(cases),
        expected_source_count,
        source_hits,
        expected_section_count,
        section_hits,
        empty_count,
        empty_pass,
        unofficial,
    )


def _base_analysis(root: Path) -> AnalysisRunResult:
    return AnalysisRunResult.model_validate_json(
        (root / "data/sample/fixtures/case-001/analysis_run_result.json").read_text(
            encoding="utf-8"
        )
    )


def _generation_review(case: dict, analysis: AnalysisRunResult) -> SpecialClauseReview:
    candidate = match_special_clauses([case["text"]])[0]
    rules = {item.rule_id: item for item in analysis.results}
    judgments = {item.judgment_id: item for item in analysis.judgments}
    if candidate.catalog_ids:
        linked_results = [
            judgments[judgment_id]
            for judgment_id in candidate.related_judgment_ids
            if judgment_id in judgments
        ] + [
            rules[rule_id]
            for rule_id in candidate.related_rule_ids
            if rule_id in rules
        ]
        source = linked_results[0]
        return SpecialClauseReview(
            clause_id="SC-EVAL-0001",
            original_text=case["text"],
            catalog_ids=candidate.catalog_ids,
            match_method=candidate.match_method,
            related_rule_ids=candidate.related_rule_ids,
            related_judgment_ids=candidate.related_judgment_ids,
            status=source.status,
            urgency=source.urgency,
            reason=source.reason,
            triggers_actions=source.triggers_actions,
            limitations=source.limitations,
        )
    source = judgments["J12"]
    return SpecialClauseReview(
        clause_id="SC-EVAL-0001",
        original_text=case["text"],
        catalog_ids=(),
        match_method="unmatched",
        related_judgment_ids=("J12",),
        status=source.status,
        urgency=source.urgency,
        reason=source.reason,
        triggers_actions=source.triggers_actions,
        limitations=source.limitations,
    )


def _generation_metrics(root: Path) -> tuple[int, int, int, int, int, int]:
    cases = _read_jsonl(
        root / "data/evaluation/special-clauses/generation_cases.jsonl"
    )
    base = _base_analysis(root)
    retrieval = build_special_clause_retrieval_service()
    output_count = grounding = prohibited = 0
    no_evidence_count = no_evidence_question_only = 0
    for case in cases:
        review = _generation_review(case, base)
        analysis = AnalysisRunResult.model_validate(
            base.model_copy(update={"special_clause_reviews": [review]}).model_dump()
        )
        if case["expect_evidence"]:
            analysis = retrieval.enrich(analysis)
        generated = GenerationService().generate(
            analysis,
            ContractContext(
                contract_id=analysis.contract_id,
                contract_type=ContractType.JEONSE,
                contract_stage=ContractStage.BEFORE_SIGNING,
                deposit_paid=False,
                signed=False,
            ),
        )
        item = generated.special_clause_items[0]
        output_count += 1
        grounding += len(
            special_clause_grounding_violations(
                analysis.special_clause_reviews[0], item
            )
        )
        texts = (
            item.plain_explanation,
            *item.confirmation_questions,
            *item.revision_requests,
        )
        prohibited += sum(
            term in text
            for term in case["prohibited_terms"]
            for text in texts
        )
        if not case["expect_evidence"]:
            no_evidence_count += 1
            no_evidence_question_only += int(
                bool(item.confirmation_questions)
                and not item.revision_requests
                and not item.source_ids
            )
    return (
        len(cases),
        output_count,
        grounding,
        prohibited,
        no_evidence_count,
        no_evidence_question_only,
    )


class _FlowEvidenceSearcher:
    def __init__(self) -> None:
        self._base = build_special_clause_retrieval_service().evidence_service

    def search(self, query, *, top_k=20, top_n=5):
        if "SC-MANAGEMENT-FEE" in query.catalog_ids:
            return EvidenceSearchResult(())
        return self._base.search(query, top_k=top_k, top_n=top_n)


def _end_to_end_metrics(root: Path) -> tuple[int, int, int, int]:
    fixture = json.loads(
        (root / "data/sample/fixtures/special-clause-rag-flow/cases.json").read_text(
            encoding="utf-8"
        )
    )
    payload = json.loads((root / fixture["base_input_snapshot"]).read_text(encoding="utf-8"))
    cases = fixture["cases"]
    contract = payload["confirmed_fields"]["contract"]
    contract["special_clauses"].update(
        extracted_value=[case["text"] for case in cases],
        user_corrected_value=None,
        normalized_value=None,
        confidence="추출됨",
        issue_code=None,
        failure_reason=None,
    )
    contract["special_clauses_present"].update(
        extracted_value=True,
        user_corrected_value=None,
        normalized_value=None,
        confidence="추출됨",
        issue_code=None,
        failure_reason=None,
    )
    snapshot = InputSnapshot.model_validate(payload)
    _, analysis, generation = analyze_special_clause_flow(
        snapshot,
        analysis_run_id="RUN-SPECIAL-OFFLINE-EVAL",
        classification_service=ClassificationService(),
        retrieval_service=SpecialClauseRetrievalService(_FlowEvidenceSearcher()),
        generation_service=GenerationService(),
    )
    reviews = {review.clause_id: review for review in analysis.special_clause_reviews}
    guidance_ids = {item.clause_id for item in generation.special_clause_items}
    review_matches = evidence_matches = guidance_coverage = 0
    for case in cases:
        review = reviews.get(case["expected_clause_id"])
        review_matches += int(
            (review is not None) is case["expect_review"]
            and (
                review is None
                or list(review.catalog_ids) == case["expected_catalog_ids"]
            )
        )
        evidence_matches += int(
            (bool(review and review.evidence_sources)) is case["expect_evidence"]
        )
        guidance_coverage += int(
            (case["expected_clause_id"] in guidance_ids) is case["expect_review"]
        )
    return len(cases), review_matches, evidence_matches, guidance_coverage


def _j10_demo_metrics(root: Path) -> tuple[int, int, int, int]:
    fixture = json.loads(
        (root / "data/sample/fixtures/special-clause-rag-flow/j10-demo.json").read_text(
            encoding="utf-8"
        )
    )
    queries: set[str] = set()
    section_sets: set[tuple[str, ...]] = set()
    revision_requests: set[str] = set()
    for case in fixture["cases"]:
        payload = json.loads(
            (root / "data/sample/fixtures/case-001/input_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        contract = payload["confirmed_fields"]["contract"]
        contract["special_clauses"].update(
            extracted_value=[case["text"]],
            user_corrected_value=None,
            normalized_value=None,
            confidence="추출됨",
            issue_code=None,
            failure_reason=None,
        )
        contract["special_clauses_present"].update(
            extracted_value=True,
            user_corrected_value=None,
            normalized_value=None,
            confidence="추출됨",
            issue_code=None,
            failure_reason=None,
        )
        snapshot = InputSnapshot.model_validate(payload)
        _, analysis, generation = analyze_special_clause_flow(
            snapshot,
            analysis_run_id=f"RUN-{case['case_id']}",
            classification_service=ClassificationService(),
            generation_service=GenerationService(),
        )
        review = analysis.special_clause_reviews[0]
        query = build_clause_retrieval_query(
            review,
            status=review.status,
            related_result_contexts=tuple(
                [*review.related_rule_ids, *review.related_judgment_ids]
            ),
        )
        queries.add(query.deidentified_clause_context)
        section_sets.add(
            tuple(
                sorted(
                    source.article_or_section or ""
                    for source in review.evidence_sources
                )
            )
        )
        item = generation.special_clause_items[0]
        revision_requests.update(item.revision_requests)
    return (
        len(fixture["cases"]),
        len(queries),
        len(section_sets),
        len(revision_requests),
    )


def evaluate_special_clause_pipeline(root: Path) -> SpecialClauseOfflineMetrics:
    """잠긴 test와 합성 종단 fixture를 API 키 없이 측정한다."""

    catalog_count, exact, normal_count, normal_fp, per_catalog = _catalog_metrics(root)
    (
        retrieval_count,
        expected_sources,
        source_hits,
        expected_sections,
        section_hits,
        empty_count,
        empty_pass,
        unofficial,
    ) = _retrieval_metrics(root)
    (
        generation_count,
        generation_outputs,
        grounding,
        prohibited,
        no_evidence_count,
        no_evidence_question_only,
    ) = _generation_metrics(root)
    e2e_count, e2e_reviews, e2e_evidence, e2e_guidance = _end_to_end_metrics(root)
    demo_count, demo_queries, demo_sections, demo_requests = _j10_demo_metrics(root)
    return SpecialClauseOfflineMetrics(
        catalog_case_count=catalog_count,
        catalog_exact_match_count=exact,
        catalog_exact_match_rate=_safe_rate(exact, catalog_count),
        normal_negative_case_count=normal_count,
        normal_negative_false_positive_count=normal_fp,
        normal_negative_false_positive_rate=_safe_rate(normal_fp, normal_count),
        per_catalog=per_catalog,
        retrieval_case_count=retrieval_count,
        expected_source_count=expected_sources,
        source_top3_hit_count=source_hits,
        source_top3_recall=_safe_rate(source_hits, expected_sources),
        expected_section_count=expected_sections,
        section_top3_hit_count=section_hits,
        section_top3_recall=_safe_rate(section_hits, expected_sections),
        empty_evidence_case_count=empty_count,
        empty_evidence_pass_count=empty_pass,
        unofficial_source_exposure_count=unofficial,
        generation_case_count=generation_count,
        generation_output_count=generation_outputs,
        generation_schema_valid_rate=_safe_rate(generation_outputs, generation_count),
        grounding_violation_count=grounding,
        prohibited_claim_count=prohibited,
        no_evidence_generation_count=no_evidence_count,
        no_evidence_question_only_count=no_evidence_question_only,
        end_to_end_fixture_count=e2e_count,
        end_to_end_review_match_count=e2e_reviews,
        end_to_end_evidence_match_count=e2e_evidence,
        end_to_end_guidance_coverage_count=e2e_guidance,
        j10_demo_case_count=demo_count,
        j10_demo_distinct_query_count=demo_queries,
        j10_demo_distinct_section_set_count=demo_sections,
        j10_demo_distinct_revision_request_count=demo_requests,
        external_provider_call_count=0,
    )
