"""어댑터(기존 평면 dict ↔ 통합 스키마) 및 R01~R10 무회귀 테스트."""

import json
import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from lease_companion_ai.extraction.minimum_mvp import parse_contract, parse_registry
from lease_companion_ai.rules.minimum_mvp import run_rules
from lease_companion_ai.schemas.adapters import (
    allowed_statuses,
    analyze_snapshot,
    apply_correction,
    apply_correction_request,
    build_snapshot,
    confirm_document,
    document_from_legacy,
    rule_inputs,
)
from lease_companion_ai.schemas.unified import (
    Confidence,
    ContractContext,
    CorrectionRequest,
    DocumentType,
    FieldCorrection,
    FieldIssueCode,
    J_FIELD_TYPES_BY_DOCUMENT,
    REQUIRED_CONTRACT_FIELDS,
    REQUIRED_REGISTRY_FIELDS,
    ResultType,
    VerificationStatus,
)

ROOT = Path(__file__).resolve().parents[3]
CONFIRMED_AT = datetime(2026, 7, 16, tzinfo=timezone.utc)

def _context(contract_id: int = 1) -> ContractContext:
    return ContractContext(
        contract_id=contract_id,
        contract_type="전세",
        contract_stage="계약금 입금 전",
        deposit_paid=False,
        signed=False,
        is_proxy_contract=False,
    )


def _load_case001_goldsets():
    def find(path: str, key="case_id", value="CASE-001"):
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record[key] == value:
                return record
        raise AssertionError(f"CASE-001 없음: {path}")

    extraction = find("data/sample/expected-results/extraction_goldset.jsonl")
    rules = find("data/sample/expected-results/rule_goldset.jsonl")
    return extraction["gold_extraction"], {
        item["rule_id"]: item["status"] for item in rules["gold_rules"]
    }


def _docs_from_gold(gold_extraction):
    contract = document_from_legacy(
        {"document_type": "contract", "fields": gold_extraction["contract"], "warnings": []},
        document_id="DOC-C",
    )
    registry = document_from_legacy(
        {"document_type": "registry_record", "fields": gold_extraction["registry"], "warnings": []},
        document_id="DOC-R",
    )
    return confirm_document(contract), confirm_document(registry)


def test_document_from_legacy_always_has_rule_field_keys():
    doc = document_from_legacy(
        {"document_type": "contract", "fields": {"landlord_name": "이정훈"}, "warnings": []},
        document_id="DOC-1",
    )
    assert REQUIRED_CONTRACT_FIELDS <= doc.fields.keys()
    missing = doc.fields["account_holder"]
    assert missing.extracted_value is None
    assert missing.confidence is Confidence.FAILED
    assert missing.failure_reason


def test_document_from_legacy_always_has_judgment_field_keys_and_issue_codes():
    contract = document_from_legacy(
        {"document_type": "contract", "fields": {"landlord_name": "이정훈"}},
        document_id="DOC-C",
    )
    registry = document_from_legacy(
        {"document_type": "registry_record", "fields": {"owner_names": ["이정훈"]}},
        document_id="DOC-R",
    )
    for doc, document_type in (
        (contract, DocumentType.CONTRACT),
        (registry, DocumentType.REGISTRY),
    ):
        assert J_FIELD_TYPES_BY_DOCUMENT[document_type].keys() <= doc.fields.keys()
        for name in J_FIELD_TYPES_BY_DOCUMENT[document_type]:
            if doc.fields[name].effective_value is None:
                assert doc.fields[name].issue_code is FieldIssueCode.UNREADABLE


def test_document_from_legacy_normalizes_empty_list_to_null():
    doc = document_from_legacy(
        {"document_type": "registry_record", "fields": {"owner_names": []}, "warnings": []},
        document_id="DOC-1",
    )
    assert doc.fields["owner_names"].extracted_value is None
    assert doc.fields["owner_names"].confidence is Confidence.FAILED


def test_apply_correction_preserves_extracted_value_and_original():
    doc = document_from_legacy(
        {"document_type": "contract", "fields": {"landlord_name": "이정문"}, "warnings": []},
        document_id="DOC-1",
    )
    original = doc.fields["landlord_name"]
    corrected = apply_correction(original, "이정훈")

    assert corrected.extracted_value == "이정문"          # 최초 추출값 보존
    assert corrected.user_corrected_value == "이정훈"
    assert corrected.verification_status is VerificationStatus.CORRECTED
    assert original.user_corrected_value is None          # 원본 객체 불변
    assert original.verification_status is VerificationStatus.UNVERIFIED


def test_rule_inputs_use_correction_then_normalized():
    doc = document_from_legacy(
        {"document_type": "contract", "fields": {"landlord_name": "이정문"}, "warnings": []},
        document_id="DOC-1",
    )
    fields = dict(doc.fields)
    fields["landlord_name"] = apply_correction(fields["landlord_name"], "이정훈")
    assert rule_inputs(fields)["landlord_name"] == "이정훈"  # 수정값 우선

    normalized = fields["property_address"].model_copy(
        update={"extracted_value": "서울시  가온구", "normalized_value": "서울특별시 가온구",
                "confidence": Confidence.EXTRACTED, "failure_reason": None}
    )
    assert normalized.effective_value == "서울특별시 가온구"  # 수정값 없으면 정규화값


def test_full_adapter_path_matches_direct_run_rules_and_goldset():
    """기존 경로(run_rules 직접 호출)와 어댑터 경로의 R01~R10 결과 동일 + goldset 유지."""
    gold_extraction, gold_statuses = _load_case001_goldsets()
    contract_doc, registry_doc = _docs_from_gold(gold_extraction)

    snapshot = build_snapshot(
        input_snapshot_id="SNAP-1",
        contract_id=1,
        case_id="CASE-001",
        contract_context=_context(),
        contract_doc=contract_doc,
        registry_doc=registry_doc,
        confirmed_at=CONFIRMED_AT,
    )
    analysis = analyze_snapshot(snapshot, analysis_run_id="RUN-1")

    direct = run_rules(
        {**gold_extraction["contract"], "is_proxy_contract": _context().is_proxy_contract},
        gold_extraction["registry"],
    )
    direct_by_id = {r.rule_id: r for r in direct}
    assert len(analysis.results) == 24
    assert [item.judgment_id for item in analysis.judgments] == [
        f"J{index:02d}" for index in range(1, 13)
    ]
    for result in analysis.results:
        legacy = direct_by_id[result.rule_id]
        assert result.status.value == legacy.status
        assert result.urgency.value == legacy.urgency
        assert result.reason == legacy.reason
        assert result.recommended_actions == legacy.recommended_actions
        assert legacy.evidence_sources == []
        assert all(source.source_id.startswith("SRC-") for source in result.evidence_sources)
        expected_type = (
            ResultType.FACT_FLAG
            if result.rule_id in {"R03", "R04", "R05", "R07", "R10"}
            else ResultType.JUDGMENT
        )
        assert result.result_type is expected_type
        assert result.triggers_actions is (
            result.status.value not in {"일치", "명확", "적용 제외"}
        )
    # CASE-001 rule goldset 유지
    assert {
        r.rule_id: r.status.value for r in analysis.results if r.rule_id in gold_statuses
    } == gold_statuses


def test_extraction_goldset_values_survive_adapter_round_trip():
    """gold extraction 값이 어댑터 통과 후 effective value로 그대로 유지된다."""
    gold_extraction, _ = _load_case001_goldsets()
    contract_doc, registry_doc = _docs_from_gold(gold_extraction)

    contract_effective = rule_inputs(contract_doc.fields)
    registry_effective = rule_inputs(registry_doc.fields)
    for name in REQUIRED_CONTRACT_FIELDS:
        assert contract_effective[name] == gold_extraction["contract"][name]
    for name in REQUIRED_REGISTRY_FIELDS:
        assert registry_effective[name] == gold_extraction["registry"][name]


def test_regex_parser_output_feeds_adapter_and_rules():
    """실제 파서 출력 → 어댑터 → 규칙 실행이 기존 직접 경로와 동일하다."""
    contract_text = (ROOT / "data/sample/contracts/contract_001.txt").read_text(encoding="utf-8")
    registry_text = (ROOT / "data/sample/registry-records/registry_001.txt").read_text(encoding="utf-8")
    legacy_contract = parse_contract(contract_text).to_dict()
    legacy_registry = parse_registry(registry_text).to_dict()

    snapshot = build_snapshot(
        input_snapshot_id="SNAP-1",
        contract_id=1,
        contract_context=_context(),
        contract_doc=confirm_document(
            document_from_legacy(legacy_contract, document_id="DOC-C")
        ),
        registry_doc=confirm_document(
            document_from_legacy(legacy_registry, document_id="DOC-R")
        ),
        confirmed_at=CONFIRMED_AT,
    )
    analysis = analyze_snapshot(snapshot, analysis_run_id="RUN-1")
    direct = {
        r.rule_id: r.status
        for r in run_rules(
            {**legacy_contract["fields"], "is_proxy_contract": _context().is_proxy_contract},
            legacy_registry["fields"],
        )
    }
    assert {r.rule_id: r.status.value for r in analysis.results} == direct


def test_analysis_statuses_stay_within_rule_spec_allowed_sets():
    gold_extraction, _ = _load_case001_goldsets()
    contract_doc, registry_doc = _docs_from_gold(gold_extraction)
    snapshot = build_snapshot(
        input_snapshot_id="SNAP-1",
        contract_id=1,
        contract_context=_context(),
        contract_doc=contract_doc,
        registry_doc=registry_doc,
        confirmed_at=CONFIRMED_AT,
    )
    for result in analyze_snapshot(snapshot, analysis_run_id="RUN-1").results:
        assert result.status in allowed_statuses(result.rule_id), result.rule_id


def test_runtime_allowed_statuses_match_rule_spec_exactly():
    with (ROOT / "data/rules/rule_spec.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        expected = set(row["result_status"].split("|"))
        assert {status.value for status in allowed_statuses(row["rule_id"])} == expected


def test_apply_correction_request_rejects_unknown_field():
    gold_extraction, _ = _load_case001_goldsets()
    contract_doc, registry_doc = _docs_from_gold(gold_extraction)
    request = CorrectionRequest(
        contract_id=1,
        corrections=[
            FieldCorrection(
                document_type=DocumentType.CONTRACT, field_name="no_such_field", corrected_value="x"
            )
        ],
    )
    with pytest.raises(KeyError):
        apply_correction_request(
            {DocumentType.CONTRACT: contract_doc, DocumentType.REGISTRY: registry_doc}, request
        )


def test_build_snapshot_requires_explicit_confirmation():
    gold_extraction, _ = _load_case001_goldsets()
    raw_contract = document_from_legacy(
        {"document_type": "contract", "fields": gold_extraction["contract"]},
        document_id="DOC-C",
    )
    raw_registry = document_from_legacy(
        {"document_type": "registry_record", "fields": gold_extraction["registry"]},
        document_id="DOC-R",
    )
    with pytest.raises(ValidationError, match="확인 완료"):
        build_snapshot(
            input_snapshot_id="SNAP-1",
            contract_id=1,
            contract_context=_context(),
            contract_doc=raw_contract,
            registry_doc=raw_registry,
            confirmed_at=CONFIRMED_AT,
        )

    snapshot = build_snapshot(
        input_snapshot_id="SNAP-1",
        contract_id=1,
        contract_context=_context(),
        contract_doc=confirm_document(raw_contract),
        registry_doc=confirm_document(raw_registry),
        confirmed_at=CONFIRMED_AT,
    )
    assert all(
        field.verification_status is VerificationStatus.CONFIRMED
        for fields in (snapshot.confirmed_fields.contract, snapshot.confirmed_fields.registry)
        for field in fields.values()
    )
