"""외부 provider 호출 없이 A 파이프라인의 결정론적 기준선을 측정한다."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from lease_companion_ai.evaluation.retrieval import (
    RetrievalMetrics,
    evaluate_retrieval,
    load_gold_cases,
)
from lease_companion_ai.extraction.minimum_mvp import parse_contract, parse_registry
from lease_companion_ai.generation.service import (
    GenerationService,
    rule_results_requiring_guidance,
)
from lease_companion_ai.evaluation.special_clauses import (
    SpecialClauseOfflineMetrics,
    evaluate_special_clause_pipeline,
)
from lease_companion_ai.guardrails.pii import PiiTokenizer, contains_raw_pii
from lease_companion_ai.guardrails.grounding import (
    grounding_violations,
    judgment_grounding_violations,
)
from lease_companion_ai.guardrails.prohibited_claims import has_prohibited_claim
from lease_companion_ai.guardrails.service import GuardrailBlocked, GuardrailService
from lease_companion_ai.rag.service import (
    EvidenceRetrievalService,
    build_evidence_service,
    load_judgment_source_ids,
    load_local_official_chunks,
)
from lease_companion_ai.rag.models import JudgmentRetrievalQuery
from lease_companion_ai.rules.judgments import run_judgments
from lease_companion_ai.rules.minimum_mvp import run_rules
from lease_companion_ai.schemas.adapters import (
    build_snapshot,
    confirm_document,
    document_from_legacy,
    rule_result_from_legacy,
)
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    ACTION_TRIGGER_STATUSES,
    Confidence,
    ContractContext,
    ContractStage,
    ContractType,
    CorrectionRequest,
    DocumentExtraction,
    DocumentType,
    ExtractedField,
    FieldIssueCode,
    GENERATION_PROMPT_VERSION,
    GenerationMethod,
    JUDGMENT_INPUT_SPECS,
    JudgmentGuidance,
    JudgmentInput,
    JudgmentResult,
    InputSnapshot,
    OfficialSource,
    RuleGuidance,
    RuleStatus,
    Urgency,
    VerificationStatus,
    build_judgment_input,
    legacy_classification_candidates,
)

_SECTIONS = ("contract", "registry")
_CONDITIONAL_NOT_APPLICABLE_FIELDS = {
    "agent_name",
    "agent_relationship",
    "proxy_authority_documents",
}
_CONTRACT_TYPES = {
    "전세": ContractType.JEONSE,
    "보증부월세": ContractType.DEPOSIT_MONTHLY,
    "보증부 월세": ContractType.DEPOSIT_MONTHLY,
    "일반월세": ContractType.MONTHLY,
    "일반 월세": ContractType.MONTHLY,
}


@dataclass(frozen=True, slots=True)
class AccuracyMetrics:
    item_count: int
    matched_count: int
    accuracy: float
    confusion_matrix: dict[str, dict[str, int]]


@dataclass(frozen=True, slots=True)
class ExtractionMetrics:
    case_count: int
    field_count: int
    matched_count: int
    accuracy: float
    schema_valid_count: int
    schema_valid_rate: float
    unreadable_field_count: int
    unreadable_representation_valid_count: int
    unreadable_representation_valid_rate: float
    per_field: dict[str, dict[str, float | int]]


@dataclass(frozen=True, slots=True)
class CorrectionEvaluationMetrics:
    correction_count: int
    original_value_preserved_count: int
    corrected_value_applied_count: int
    corrected_status_count: int
    pass_rate: float


@dataclass(frozen=True, slots=True)
class PiiEvaluationMetrics:
    case_count: int
    tokenized_without_raw_count: int
    restored_exact_count: int
    tokenization_pass_rate: float
    restoration_pass_rate: float


@dataclass(frozen=True, slots=True)
class RuleEvaluationMetrics:
    case_count: int
    rule_count: int
    status: AccuracyMetrics
    urgency: AccuracyMetrics


@dataclass(frozen=True, slots=True)
class JudgmentEvaluationMetrics:
    case_count: int
    judgment_count: int
    status: AccuracyMetrics
    urgency: AccuracyMetrics
    per_judgment: dict[str, dict[str, float | int]]


@dataclass(frozen=True, slots=True)
class JudgmentRetrievalEvaluationMetrics:
    query_count: int
    expected_source_count: int
    locally_available_expected_source_count: int
    retrieved_expected_source_count: int
    expected_source_recall: float
    unofficial_source_exposure_count: int


@dataclass(frozen=True, slots=True)
class GenerationEvaluationMetrics:
    case_count: int
    schema_valid_count: int
    schema_valid_rate: float
    active_rule_count: int
    guidance_item_count: int
    trigger_coverage_rate: float
    active_judgment_count: int
    judgment_guidance_item_count: int
    judgment_trigger_coverage_rate: float
    expected_prompt_version: str
    prompt_version_match_count: int
    analysis_immutable_count: int
    analysis_immutable_rate: float
    template_fallback_count: int
    missing_evidence_fallback_count: int
    grounding_violation_count: int
    judgment_grounding_violation_count: int
    prohibited_claim_count: int
    provider_call_count: int
    subjective_quality: str


@dataclass(frozen=True, slots=True)
class GuardrailEvaluationMetrics:
    case_count: int
    rule_case_count: int
    judgment_case_count: int
    blocked_count: int
    expected_reason_match_count: int
    expected_reason_match_rate: float
    false_negative_count: int


@dataclass(frozen=True, slots=True)
class EndToEndMetrics:
    case_count: int
    completed_case_count: int
    completion_rate: float
    elapsed_seconds: float
    mean_seconds_per_case: float
    external_provider_call_count: int
    external_provider_cost_krw: int


@dataclass(frozen=True, slots=True)
class OfflineEvaluationReport:
    measured_at: str
    config_version: str
    split: str
    extraction: ExtractionMetrics
    corrections: CorrectionEvaluationMetrics
    rules: RuleEvaluationMetrics
    judgments: JudgmentEvaluationMetrics
    retrieval: RetrievalMetrics
    judgment_retrieval: JudgmentRetrievalEvaluationMetrics
    generation: GenerationEvaluationMetrics
    guardrail: GuardrailEvaluationMetrics
    pii: PiiEvaluationMetrics
    special_clauses: SpecialClauseOfflineMetrics
    end_to_end: EndToEndMetrics
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _normalized(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value.replace(",", " ")).strip()
    if isinstance(value, list):
        return sorted(_normalized(item) for item in value)
    return value


def _accuracy(
    expected_actual: list[tuple[str, str]],
) -> AccuracyMetrics:
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    matched = 0
    for expected, actual in expected_actual:
        confusion[expected][actual] += 1
        matched += int(expected == actual)
    count = len(expected_actual)
    return AccuracyMetrics(
        item_count=count,
        matched_count=matched,
        accuracy=matched / count if count else 0.0,
        confusion_matrix={
            expected: dict(sorted(actual.items()))
            for expected, actual in sorted(confusion.items())
        },
    )


def _offline_extractions(
    root: Path, records: list[dict[str, Any]]
) -> dict[str, dict[str, dict[str, Any]]]:
    base = root / "data" / "evaluation" / "end-to-end"
    predictions: dict[str, dict[str, dict[str, Any]]] = {}
    for record in records:
        contract_text = (base / "contracts" / record["contract_file"]).read_text(
            encoding="utf-8"
        )
        registry_text = (base / "registry-records" / record["registry_file"]).read_text(
            encoding="utf-8"
        )
        predictions[record["case_id"]] = {
            "contract": parse_contract(contract_text).fields,
            "registry": parse_registry(registry_text).fields,
        }
    return predictions


def _evaluate_extraction(
    records: list[dict[str, Any]],
    predictions: dict[str, dict[str, dict[str, Any]]],
) -> ExtractionMetrics:
    matched = 0
    total = 0
    schema_valid = 0
    unreadable = 0
    unreadable_valid = 0
    per_field: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for record in records:
        predicted = predictions[record["case_id"]]
        for section, document_type in (
            ("contract", "contract"),
            ("registry", "registry_record"),
        ):
            document = document_from_legacy(
                {"document_type": document_type, "fields": predicted[section]},
                document_id=f"EVAL-{record['case_id']}-{section}",
            )
            schema_valid += 1
            for field, expected in record["gold_extraction"][section].items():
                actual = predicted[section].get(field, object())
                ok = _normalized(actual) == _normalized(expected)
                key = f"{section}.{field}"
                per_field[key][1] += 1
                total += 1
                if ok:
                    per_field[key][0] += 1
                    matched += 1
                if expected is None:
                    unreadable += 1
                    extracted = document.fields[field]
                    valid_absence = extracted.confidence is Confidence.FAILED or (
                        section == "contract"
                        and field in _CONDITIONAL_NOT_APPLICABLE_FIELDS
                        and extracted.confidence is Confidence.UNCERTAIN
                        and extracted.issue_code is FieldIssueCode.NOT_APPLICABLE
                    )
                    unreadable_valid += int(
                        extracted.extracted_value is None
                        and valid_absence
                        and bool(extracted.failure_reason)
                    )
    document_count = len(records) * len(_SECTIONS)
    return ExtractionMetrics(
        case_count=len(records),
        field_count=total,
        matched_count=matched,
        accuracy=matched / total if total else 0.0,
        schema_valid_count=schema_valid,
        schema_valid_rate=schema_valid / document_count if document_count else 0.0,
        unreadable_field_count=unreadable,
        unreadable_representation_valid_count=unreadable_valid,
        unreadable_representation_valid_rate=(
            unreadable_valid / unreadable if unreadable else 1.0
        ),
        per_field={
            field: {
                "matched_count": counts[0],
                "item_count": counts[1],
                "accuracy": counts[0] / counts[1],
            }
            for field, counts in sorted(per_field.items())
        },
    )


def _evaluate_corrections(root: Path) -> CorrectionEvaluationMetrics:
    fixture_root = root / "data" / "sample" / "fixtures" / "case-001"
    contract = DocumentExtraction.model_validate_json(
        (fixture_root / "contract_extraction.json").read_text(encoding="utf-8")
    )
    registry = DocumentExtraction.model_validate_json(
        (fixture_root / "registry_extraction.json").read_text(encoding="utf-8")
    )
    request = CorrectionRequest.model_validate_json(
        (fixture_root / "correction_request.json").read_text(encoding="utf-8")
    )
    snapshot = InputSnapshot.model_validate_json(
        (fixture_root / "input_snapshot.json").read_text(encoding="utf-8")
    )
    source_documents = {
        DocumentType.CONTRACT: contract,
        DocumentType.REGISTRY: registry,
    }
    snapshot_fields = {
        DocumentType.CONTRACT: snapshot.confirmed_fields.contract,
        DocumentType.REGISTRY: snapshot.confirmed_fields.registry,
    }
    original_preserved = 0
    corrected_applied = 0
    corrected_status = 0
    for correction in request.corrections:
        original = source_documents[correction.document_type].fields[
            correction.field_name
        ]
        corrected = snapshot_fields[correction.document_type][correction.field_name]
        original_preserved += int(corrected.extracted_value == original.extracted_value)
        corrected_applied += int(
            corrected.user_corrected_value == correction.corrected_value
            and corrected.effective_value == correction.corrected_value
        )
        corrected_status += int(
            corrected.verification_status is VerificationStatus.CORRECTED
        )
    count = len(request.corrections)
    passed = original_preserved + corrected_applied + corrected_status
    checks = count * 3
    return CorrectionEvaluationMetrics(
        correction_count=count,
        original_value_preserved_count=original_preserved,
        corrected_value_applied_count=corrected_applied,
        corrected_status_count=corrected_status,
        pass_rate=passed / checks if checks else 1.0,
    )


def _evaluate_pii(root: Path) -> PiiEvaluationMetrics:
    cases = _read_jsonl(root / "data" / "evaluation" / "generation" / "pii_cases.jsonl")
    tokenized_without_raw = 0
    restored_exact = 0
    for case in cases:
        tokenizer = PiiTokenizer()
        tokenized = tokenizer.tokenize(case["text"])
        if tokenized is None:
            continue
        tokenized_without_raw += int(not contains_raw_pii(tokenized))
        restored_exact += int(tokenizer.restore(tokenized) == case["text"])
    count = len(cases)
    return PiiEvaluationMetrics(
        case_count=count,
        tokenized_without_raw_count=tokenized_without_raw,
        restored_exact_count=restored_exact,
        tokenization_pass_rate=tokenized_without_raw / count if count else 1.0,
        restoration_pass_rate=restored_exact / count if count else 1.0,
    )


def _evaluate_rules(
    records: list[dict[str, Any]],
    predictions: dict[str, dict[str, dict[str, Any]]],
) -> RuleEvaluationMetrics:
    statuses: list[tuple[str, str]] = []
    urgencies: list[tuple[str, str]] = []
    for record in records:
        actual = {
            result.rule_id: result
            for result in run_rules(
                predictions[record["case_id"]]["contract"],
                predictions[record["case_id"]]["registry"],
            )
        }
        for expected in record["gold_rules"]:
            result = actual[expected["rule_id"]]
            statuses.append((expected["status"], result.status))
            if expected.get("urgency") is not None:
                urgencies.append((expected["urgency"], result.urgency))
    return RuleEvaluationMetrics(
        case_count=len(records),
        rule_count=len(statuses),
        status=_accuracy(statuses),
        urgency=_accuracy(urgencies),
    )


def _confirmed_field(name: str, payload: dict[str, Any]) -> ExtractedField:
    value = payload["value"]
    issue = payload.get("issue_code")
    confidence = (
        Confidence.FAILED
        if value is None
        else Confidence.UNCERTAIN
        if issue == FieldIssueCode.AMBIGUOUS.value
        else Confidence.EXTRACTED
    )
    return ExtractedField(
        field_name=name,
        extracted_value=value,
        verification_status=VerificationStatus.CONFIRMED,
        confidence=confidence,
        issue_code=issue,
        failure_reason=f"goldset:{issue}" if value is None else None,
    )


def _evaluate_judgments(root: Path) -> JudgmentEvaluationMetrics:
    records = _read_jsonl(
        root / "data" / "sample" / "expected-results" / "judgment_goldset.jsonl"
    )
    statuses: list[tuple[str, str]] = []
    urgencies: list[tuple[str, str]] = []
    per_judgment: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for record in records:
        judgment_id = record["judgment_id"]
        for case in record["cases"]:
            context = ContractContext(
                **{**record["base_context"], **case.get("context_overrides", {})}
            )
            contract_fields = {
                name: _confirmed_field(name, payload)
                for name, payload in case["contract_fields"].items()
            }
            classification_candidates = legacy_classification_candidates(
                contract_fields
            )
            required_contract_fields = set(
                JUDGMENT_INPUT_SPECS[judgment_id].contract_fields
            )
            judgment_input = JudgmentInput(
                schema_version=context.schema_version,
                input_snapshot_id=f"SNAP-{case['case_id']}",
                contract_id=context.contract_id,
                case_id=case["case_id"],
                judgment_ids=(judgment_id,),
                contract_context=context,
                contract_fields={
                    name: field
                    for name, field in contract_fields.items()
                    if name in required_contract_fields
                },
                registry_fields={
                    name: _confirmed_field(name, payload)
                    for name, payload in case["registry_fields"].items()
                },
                classification_candidates=[
                    candidate
                    for candidate in classification_candidates
                    if candidate.clause_ref.partition(":")[0]
                    in required_contract_fields
                ],
            )
            result = run_judgments(judgment_input)[0]
            expected_status = case["expected_status"]
            statuses.append((expected_status, result.status.value))
            urgencies.append((case["expected_urgency"], result.urgency.value))
            per_judgment[judgment_id][1] += 1
            per_judgment[judgment_id][0] += int(expected_status == result.status.value)
    return JudgmentEvaluationMetrics(
        case_count=len(statuses),
        judgment_count=len(records),
        status=_accuracy(statuses),
        urgency=_accuracy(urgencies),
        per_judgment={
            judgment_id: {
                "matched_count": counts[0],
                "item_count": counts[1],
                "accuracy": counts[0] / counts[1],
            }
            for judgment_id, counts in sorted(per_judgment.items())
        },
    )


def _context(record: dict[str, Any], index: int) -> ContractContext:
    return ContractContext(
        contract_id=index + 1,
        contract_type=_CONTRACT_TYPES[record["contract_type"]],
        contract_stage=ContractStage.BEFORE_SIGNING,
        deposit_paid=False,
        signed=False,
        is_proxy_contract=None,
    )


def _analyses(
    records: list[dict[str, Any]],
    predictions: dict[str, dict[str, dict[str, Any]]],
    service: EvidenceRetrievalService,
) -> list[tuple[AnalysisRunResult, ContractContext]]:
    analyses: list[tuple[AnalysisRunResult, ContractContext]] = []
    for index, record in enumerate(records):
        context = _context(record, index)
        legacy = run_rules(
            predictions[record["case_id"]]["contract"],
            predictions[record["case_id"]]["registry"],
        )
        contract_document = confirm_document(
            document_from_legacy(
                {
                    "document_type": "contract",
                    "fields": predictions[record["case_id"]]["contract"],
                },
                document_id=f"EVAL-{record['case_id']}-CONTRACT",
            )
        )
        registry_document = confirm_document(
            document_from_legacy(
                {
                    "document_type": "registry_record",
                    "fields": predictions[record["case_id"]]["registry"],
                },
                document_id=f"EVAL-{record['case_id']}-REGISTRY",
            )
        )
        snapshot = build_snapshot(
            input_snapshot_id=f"EVAL-SNAPSHOT-{record['case_id']}",
            contract_id=context.contract_id,
            case_id=record["case_id"],
            contract_context=context,
            contract_doc=contract_document,
            registry_doc=registry_document,
            confirmed_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        )
        analysis = AnalysisRunResult(
            analysis_run_id=f"EVAL-RUN-{record['case_id']}",
            input_snapshot_id=f"EVAL-SNAPSHOT-{record['case_id']}",
            contract_id=context.contract_id,
            case_id=record["case_id"],
            results=[rule_result_from_legacy(result) for result in legacy],
            judgments=run_judgments(build_judgment_input(snapshot)),
        )
        analyses.append((service.enrich(analysis), context))
    return analyses


def _evaluate_generation(
    analyses: list[tuple[AnalysisRunResult, ContractContext]],
) -> GenerationEvaluationMetrics:
    generator = GenerationService()
    schema_valid = 0
    active = 0
    guidance_count = 0
    active_judgments = 0
    judgment_guidance_count = 0
    prompt_matches = 0
    immutable = 0
    fallbacks = 0
    missing_evidence = 0
    grounding = 0
    judgment_grounding = 0
    prohibited = 0
    for analysis, context in analyses:
        before = analysis.model_dump(mode="json")
        generation = generator.generate(analysis, context)
        immutable += int(analysis.model_dump(mode="json") == before)
        generation.__class__.model_validate(generation.model_dump(mode="json"))
        schema_valid += 1
        prompt_matches += int(
            generation.prompt_version == GENERATION_PROMPT_VERSION
        )
        rules = {result.rule_id: result for result in analysis.results}
        judgments = {result.judgment_id: result for result in analysis.judgments}
        active += len(rule_results_requiring_guidance(analysis))
        active_judgments += sum(
            result.triggers_actions for result in analysis.judgments
        )
        guidance_count += len(generation.items)
        judgment_guidance_count += len(generation.judgment_items)
        for rule_item in generation.items:
            fallbacks += int(
                rule_item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
            )
            missing_evidence += int(rule_item.fallback_reason == "missing_evidence")
            grounding += len(grounding_violations(rules[rule_item.rule_id], rule_item))
            prohibited += int(
                has_prohibited_claim(
                    (
                        rule_item.explanation,
                        *rule_item.questions,
                        *rule_item.signing_checklist,
                        *rule_item.post_contract_actions,
                    )
                )
            )
        for judgment_item in generation.judgment_items:
            fallbacks += int(
                judgment_item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
            )
            missing_evidence += int(judgment_item.fallback_reason == "missing_evidence")
            judgment_grounding += len(
                judgment_grounding_violations(
                    judgments[judgment_item.judgment_id], judgment_item
                )
            )
            prohibited += int(
                has_prohibited_claim(
                    (
                        judgment_item.explanation,
                        *judgment_item.questions,
                        *judgment_item.signing_checklist,
                        *judgment_item.post_contract_actions,
                    )
                )
            )
    case_count = len(analyses)
    return GenerationEvaluationMetrics(
        case_count=case_count,
        schema_valid_count=schema_valid,
        schema_valid_rate=schema_valid / case_count if case_count else 0.0,
        active_rule_count=active,
        guidance_item_count=guidance_count,
        trigger_coverage_rate=guidance_count / active if active else 1.0,
        active_judgment_count=active_judgments,
        judgment_guidance_item_count=judgment_guidance_count,
        judgment_trigger_coverage_rate=(
            judgment_guidance_count / active_judgments if active_judgments else 1.0
        ),
        expected_prompt_version=GENERATION_PROMPT_VERSION,
        prompt_version_match_count=prompt_matches,
        analysis_immutable_count=immutable,
        analysis_immutable_rate=(immutable / case_count if case_count else 1.0),
        template_fallback_count=fallbacks,
        missing_evidence_fallback_count=missing_evidence,
        grounding_violation_count=grounding,
        judgment_grounding_violation_count=judgment_grounding,
        prohibited_claim_count=prohibited,
        provider_call_count=0,
        subjective_quality="not_measured:no_human_or_independent_judge_labels",
    )


def _evaluate_judgment_retrieval(
    root: Path, service: EvidenceRetrievalService
) -> JudgmentRetrievalEvaluationMetrics:
    records = _read_jsonl(
        root / "data" / "sample" / "expected-results" / "judgment_goldset.jsonl"
    )
    source_ids = load_judgment_source_ids(root)
    local_source_ids = {
        chunk.metadata.source_id for chunk in load_local_official_chunks(root)
    }
    query_count = 0
    expected_count = 0
    available_count = 0
    retrieved_count = 0
    unofficial_count = 0
    for record in records:
        judgment_id = record["judgment_id"]
        allowed = source_ids[judgment_id]
        for case in record["cases"]:
            status = RuleStatus(case["expected_status"])
            if status not in ACTION_TRIGGER_STATUSES:
                continue
            query_count += 1
            expected_count += len(allowed)
            available_count += len(set(allowed) & local_source_ids)
            result = service.search(
                JudgmentRetrievalQuery(
                    judgment_id=judgment_id,
                    judgment_name=record["judgment_name"],
                    status=status,
                    allowed_source_ids=allowed,
                )
            )
            retrieved = {hit.chunk.metadata.source_id for hit in result.hits}
            retrieved_count += len(retrieved & set(allowed))
            unofficial_count += sum(
                hit.chunk.metadata.source_status != "official_verified"
                for hit in result.hits
            )
    return JudgmentRetrievalEvaluationMetrics(
        query_count=query_count,
        expected_source_count=expected_count,
        locally_available_expected_source_count=available_count,
        retrieved_expected_source_count=retrieved_count,
        expected_source_recall=(
            retrieved_count / expected_count if expected_count else 0.0
        ),
        unofficial_source_exposure_count=unofficial_count,
    )


def _guardrail_rule(with_evidence: bool) -> Any:
    result = rule_result_from_legacy(
        run_rules(
            {"landlord_name": "임대인", "account_holder": "다른 명의"},
            {"owner_names": ["임대인"]},
        )[5]
    )
    if not with_evidence:
        return result
    source = OfficialSource(
        source_id="SRC-EVAL-001",
        title="합성 공식 근거",
        institution="평가기관",
        summary="평가용 근거 요약",
        source_url="https://example.go.kr/eval",
    )
    return result.model_copy(update={"evidence_sources": [source]})


def _guardrail_judgment(with_evidence: bool) -> JudgmentResult:
    source = OfficialSource(
        source_id="SRC-EVAL-001",
        title="합성 공식 근거",
        institution="평가기관",
        summary="평가용 근거 요약",
        source_url="https://example.go.kr/eval",
    )
    return JudgmentResult(
        judgment_id="J01",
        judgment_name="계약서 임대인=등기 소유자",
        status=RuleStatus.MISMATCH,
        urgency=Urgency.IMMEDIATE,
        triggers_actions=True,
        reason="임대인과 소유자가 다릅니다.",
        question="계약 상대 권한을 확인했습니까?",
        recommended_actions=["소유자 자료를 확인하십시오."],
        evidence_sources=[source] if with_evidence else [],
        limitations="이름 비교만 수행합니다.",
    )


def _evaluate_guardrail(root: Path) -> GuardrailEvaluationMetrics:
    cases = _read_jsonl(
        root / "data" / "evaluation" / "generation" / "guardrail_cases.jsonl"
    )
    service = GuardrailService()
    blocked = 0
    reason_matches = 0
    false_negatives = 0
    for case in cases:
        rule = _guardrail_rule(case["with_evidence"])
        guidance = RuleGuidance(
            rule_id=rule.rule_id,
            explanation=case["explanation"],
            signing_checklist=tuple(case.get("signing_checklist", ())),
            source_ids=tuple(case.get("source_ids", ())),
            generation_method=GenerationMethod.TEMPLATE_FALLBACK,
            fallback_reason="adversarial_fixture",
        )
        actual_reasons: tuple[str, ...] = ()
        try:
            service.enforce(rule, guidance)
        except GuardrailBlocked as exc:
            blocked += 1
            actual_reasons = exc.reasons
        expected = tuple(case["expected_reasons"])
        reason_matches += int(set(actual_reasons) == set(expected))
        false_negatives += int(bool(expected) and not actual_reasons)
        judgment = _guardrail_judgment(case["with_evidence"])
        judgment_guidance = JudgmentGuidance(
            judgment_id=judgment.judgment_id,
            explanation=case["explanation"],
            signing_checklist=tuple(case.get("signing_checklist", ())),
            source_ids=tuple(case.get("source_ids", ())),
            generation_method=GenerationMethod.TEMPLATE_FALLBACK,
            fallback_reason="adversarial_fixture",
        )
        actual_reasons = ()
        try:
            service.enforce_judgment(judgment, judgment_guidance)
        except GuardrailBlocked as exc:
            blocked += 1
            actual_reasons = exc.reasons
        reason_matches += int(set(actual_reasons) == set(expected))
        false_negatives += int(bool(expected) and not actual_reasons)
    count = len(cases) * 2
    return GuardrailEvaluationMetrics(
        case_count=count,
        rule_case_count=len(cases),
        judgment_case_count=len(cases),
        blocked_count=blocked,
        expected_reason_match_count=reason_matches,
        expected_reason_match_rate=reason_matches / count if count else 0.0,
        false_negative_count=false_negatives,
    )


def evaluate_offline_pipeline(
    root: Path,
    *,
    measured_at: date,
    config_version: str = "offline-regex-bm25-template-v3",
) -> OfflineEvaluationReport:
    """잠금 test/goldset으로 외부 호출 없는 기준선을 생성한다."""
    extraction_records = _read_jsonl(
        root / "data" / "evaluation" / "end-to-end" / "final_testset_extraction.jsonl"
    )
    rule_records = _read_jsonl(
        root / "data" / "evaluation" / "end-to-end" / "final_testset_rule.jsonl"
    )
    if [record["case_id"] for record in extraction_records] != [
        record["case_id"] for record in rule_records
    ]:
        raise ValueError("추출·규칙 testset의 case_id 순서가 다릅니다.")

    started = perf_counter()
    predictions = _offline_extractions(root, extraction_records)
    local_chunks = load_local_official_chunks(root)
    service = build_evidence_service(local_chunks)
    locally_available_source_ids = {chunk.metadata.source_id for chunk in local_chunks}
    analyses = _analyses(rule_records, predictions, service)
    generation = _evaluate_generation(analyses)
    elapsed = perf_counter() - started

    rag_cases = load_gold_cases(
        root / "data" / "evaluation" / "end-to-end" / "final_testset_rag.jsonl",
        root / "data" / "evaluation" / "end-to-end" / "final_testset_rule.jsonl",
        root / "data" / "rules" / "rule_spec.csv",
        root / "data" / "rules" / "rule_evidence_map.csv",
    )
    retrieval = evaluate_retrieval(
        rag_cases,
        service,
        split="test",
        measured_at=measured_at,
        config_version=config_version,
        locally_available_source_ids=locally_available_source_ids,
        top_k=5,
    )
    case_count = len(extraction_records)
    return OfflineEvaluationReport(
        measured_at=measured_at.isoformat(),
        config_version=config_version,
        split="test",
        extraction=_evaluate_extraction(extraction_records, predictions),
        corrections=_evaluate_corrections(root),
        rules=_evaluate_rules(rule_records, predictions),
        judgments=_evaluate_judgments(root),
        retrieval=retrieval,
        judgment_retrieval=_evaluate_judgment_retrieval(root, service),
        generation=generation,
        guardrail=_evaluate_guardrail(root),
        pii=_evaluate_pii(root),
        special_clauses=evaluate_special_clause_pipeline(root),
        end_to_end=EndToEndMetrics(
            case_count=case_count,
            completed_case_count=len(analyses),
            completion_rate=len(analyses) / case_count if case_count else 0.0,
            elapsed_seconds=round(elapsed, 6),
            mean_seconds_per_case=round(elapsed / case_count, 6),
            external_provider_call_count=0,
            external_provider_cost_krw=0,
        ),
        limitations=(
            "추출 지표는 Gemini 3.5 Flash가 아닌 로컬 정규식 fallback 기준선입니다.",
            "검색 지표는 외부 embedding·rerank 없이 로컬 BM25만 측정했습니다.",
            "생성 지표는 template fallback의 구조·grounding·금지 단정만 측정했습니다.",
            "쉬운 설명의 주관 품질은 사람 또는 독립 judge 라벨이 없어 측정하지 않았습니다.",
            "실제 provider latency와 비용은 외부 호출 승인이 없어 측정하지 않았습니다.",
        ),
    )
