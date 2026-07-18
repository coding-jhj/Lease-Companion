"""통합 스키마(unified.py) 검증 규칙 테스트."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from lease_companion_ai.schemas.unified import (
    SCHEMA_VERSION,
    AnalysisRunResult,
    Confidence,
    ContractContext,
    DocumentExtraction,
    DocumentType,
    ExtractedField,
    FieldCorrection,
    GenerationMethod,
    GenerationResult,
    InputSnapshot,
    JudgmentInput,
    JudgmentGuidance,
    JudgmentResult,
    JUDGMENT_IDS,
    JUDGMENT_INPUT_SPECS,
    OfficialSource,
    ResultType,
    RuleGuidance,
    RuleResult,
    SnapshotFields,
    StageGuidance,
    SourceEvidence,
    Urgency,
    VerificationStatus,
    build_judgment_input,
    validate_generation_result_for_analysis,
)


def _field(name: str = "landlord_name", value="이정훈", **overrides) -> ExtractedField:
    payload = {
        "field_name": name,
        "extracted_value": value,
        "confidence": Confidence.EXTRACTED,
    }
    payload.update(overrides)
    return ExtractedField(**payload)


def _contract_fields(**overrides) -> dict[str, ExtractedField]:
    values = {
        "landlord_name": "이정훈",
        "property_address": "서울특별시 가온구 나래로 12",
        "account_holder": "이정훈",
        "deposit_return_condition": "명확",
        "repair_responsibility": "명확",
        "rights_change_clause_present": True,
    }
    values.update(overrides)
    return {name: _field(name, value) for name, value in values.items()}


def _registry_fields() -> dict[str, ExtractedField]:
    values = {
        "owner_names": ["박성우"],
        "property_address": "서울특별시 가온구 나래로 12",
        "issue_date": "2026-07-28",
        "mortgage_present": True,
        "seizure_present": False,
        "provisional_seizure_present": False,
        "trust_present": False,
    }
    return {name: _field(name, value) for name, value in values.items()}


# --- ExtractedField ---

def test_rejects_wrong_nested_value_type():
    with pytest.raises(ValidationError):
        _field(value={"owner": 1})


def test_accepts_and_freezes_string_mapping_value():
    field = _field(name="owner_shares", value={"박성우": "1/1"})
    assert field.effective_value == {"박성우": "1/1"}
    with pytest.raises(TypeError):
        field.extracted_value["박성우"] = "1/2"


def test_rejects_numeric_confidence():
    with pytest.raises(ValidationError):
        _field(confidence=0.9)


def test_accepts_exactly_three_confidence_grades():
    assert _field(confidence="추출됨").confidence is Confidence.EXTRACTED
    assert _field(
        confidence="불확실"
    ).confidence is Confidence.UNCERTAIN
    failed = ExtractedField(field_name="x", confidence="실패", failure_reason="판독 불가")
    assert failed.confidence is Confidence.FAILED
    with pytest.raises(ValidationError):
        _field(confidence="높음")


def test_rejects_unknown_verification_status():
    with pytest.raises(ValidationError):
        _field(verification_status="approved")


def test_source_evidence_allows_null_page_and_text():
    field = _field()
    assert field.source_evidence.page is None
    assert field.source_evidence.text is None
    explicit = SourceEvidence(page=None, text=None)
    assert explicit.model_dump() == {"page": None, "text": None}


def test_failed_extraction_requires_failure_reason_and_allows_null_value():
    ok = ExtractedField(field_name="account_holder", confidence="실패", failure_reason="판독 불가")
    assert ok.extracted_value is None
    with pytest.raises(ValidationError):
        ExtractedField(field_name="account_holder", confidence="실패")


def test_extracted_confidence_requires_value():
    with pytest.raises(ValidationError):
        ExtractedField(field_name="landlord_name", confidence="추출됨")


def test_corrected_status_requires_corrected_value():
    with pytest.raises(ValidationError):
        _field(verification_status=VerificationStatus.CORRECTED)


def test_rejects_empty_owner_names_list():
    with pytest.raises(ValidationError):
        _field(name="owner_names", value=[])


def test_effective_value_priority():
    corrected = _field(
        normalized_value="이 정훈",
        user_corrected_value="김정훈",
        verification_status=VerificationStatus.CORRECTED,
    )
    assert corrected.effective_value == "김정훈"
    normalized = _field(normalized_value="이 정훈")
    assert normalized.effective_value == "이 정훈"
    plain = _field()
    assert plain.effective_value == "이정훈"


# --- DocumentExtraction / InputSnapshot ---

def test_document_requires_all_rule_field_keys():
    fields = _contract_fields()
    del fields["account_holder"]
    with pytest.raises(ValidationError, match="account_holder"):
        DocumentExtraction(document_id="D1", document_type=DocumentType.CONTRACT, fields=fields)


def test_document_rejects_key_field_name_mismatch():
    fields = _contract_fields()
    fields["landlord_name"] = _field("tenant_name", "강해린")
    with pytest.raises(ValidationError):
        DocumentExtraction(document_id="D1", document_type=DocumentType.CONTRACT, fields=fields)


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("landlord_name", 123),
        ("rights_change_clause_present", "true"),
    ],
)
def test_contract_rule_fields_enforce_canonical_types(field_name, bad_value):
    fields = _contract_fields()
    fields[field_name] = _field(field_name, bad_value)
    with pytest.raises(ValidationError, match=field_name):
        DocumentExtraction(document_id="D1", document_type=DocumentType.CONTRACT, fields=fields)


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("owner_names", "박성우"),
        ("issue_date", True),
        ("mortgage_present", "false"),
    ],
)
def test_registry_rule_fields_enforce_canonical_types(field_name, bad_value):
    fields = _registry_fields()
    fields[field_name] = _field(field_name, bad_value)
    with pytest.raises(ValidationError, match=field_name):
        DocumentExtraction(document_id="D1", document_type=DocumentType.REGISTRY, fields=fields)


def test_correction_request_enforces_rule_field_type():
    with pytest.raises(ValidationError, match="mortgage_present"):
        FieldCorrection(
            document_type=DocumentType.REGISTRY,
            field_name="mortgage_present",
            corrected_value="false",
        )


def test_models_reject_unknown_schema_version():
    assert SCHEMA_VERSION == "1.9.0"
    with pytest.raises(ValidationError):
        ContractContext(
            schema_version="1.0.0",
            contract_id=1,
            contract_type="전세",
            contract_stage="계약금 입금 전",
            deposit_paid=False,
            signed=False,
        )



def _context(contract_id: int = 1) -> ContractContext:
    return ContractContext(
        contract_id=contract_id,
        contract_type="전세",
        contract_stage="계약금 입금 전",
        deposit_paid=False,
        signed=False,
        is_proxy_contract=False,
    )

def _snapshot(contract_id=1, case_id=None, status=VerificationStatus.CONFIRMED):
    contract = {
        name: field.model_copy(update={"verification_status": status})
        for name, field in _contract_fields().items()
    }
    registry = {
        name: field.model_copy(update={"verification_status": status})
        for name, field in _registry_fields().items()
    }
    return InputSnapshot(
        input_snapshot_id="SNAP-1",
        contract_id=contract_id,
        case_id=case_id,
        contract_context=_context(contract_id),
        confirmed_fields=SnapshotFields(contract=contract, registry=registry),
        confirmed_at=datetime(2026, 7, 16, tzinfo=timezone.utc),
    )


def _judgment_snapshot(*, remove_contract=(), remove_registry=()) -> InputSnapshot:
    snapshot = _snapshot()
    contract_values = {
        "agent_name": "박대리",
        "agent_relationship": "가족",
        "proxy_authority_documents": ["위임장", "인감증명서"],
        "deposit": 100_000_000,
        "deposit_korean_amount": 100_000_000,
        "monthly_rent": 0,
        "monthly_rent_korean_amount": 0,
        "contract_payment": 10_000_000,
        "contract_payment_korean_amount": 10_000_000,
        "balance_payment": 90_000_000,
        "balance_payment_korean_amount": 90_000_000,
        "contract_payment_date": "2026-07-18",
        "balance_payment_date": "2026-08-31",
        "move_in_date": "2026-08-31",
        "start_date": "2026-08-31",
        "end_date": "2028-08-30",
        "management_fee_present": True,
        "management_fee": 100_000,
        "management_fee_items": ["수도", "공용전기"],
        "deposit_return_clause": "계약 종료일에 보증금을 반환한다.",
        "repair_responsibility_clause": "주요 설비 수리는 임대인이 부담한다.",
        "main_clauses": ["계약기간은 2026-08-31부터 2028-08-30까지다."],
        "special_clauses_present": True,
        "special_clauses": ["계약기간은 본문과 동일하다."],
    }
    registry_values = {
        "is_joint_ownership": False,
        "owner_shares": {"박성우": "1/1"},
    }
    contract = dict(snapshot.confirmed_fields.contract)
    registry = dict(snapshot.confirmed_fields.registry)
    contract.update(
        {
            name: _field(name, value, verification_status=VerificationStatus.CONFIRMED)
            for name, value in contract_values.items()
            if name not in remove_contract
        }
    )
    registry.update(
        {
            name: _field(name, value, verification_status=VerificationStatus.CONFIRMED)
            for name, value in registry_values.items()
            if name not in remove_registry
        }
    )
    return snapshot.model_copy(
        update={"confirmed_fields": SnapshotFields(contract=contract, registry=registry)}
    )


def test_judgment_input_specs_cover_all_judgments_and_known_fields():
    assert tuple(JUDGMENT_INPUT_SPECS) == JUDGMENT_IDS
    assert JUDGMENT_INPUT_SPECS["J03"].registry_fields == (
        "owner_names",
        "is_joint_ownership",
        "owner_shares",
    )
    assert JUDGMENT_INPUT_SPECS["J04"].context_fields == ("is_proxy_contract",)
    assert JUDGMENT_INPUT_SPECS["J08"].context_fields == (
        "move_in_date",
        "balance_payment_date",
    )


def test_build_judgment_input_selects_exact_required_effective_values():
    result = build_judgment_input(_judgment_snapshot(), judgment_ids=("J03",))
    assert isinstance(result, JudgmentInput)
    assert result.judgment_ids == ("J03",)
    assert result.contract_fields == {}
    assert {
        name: field.effective_value for name, field in result.registry_fields.items()
    } == {
        "owner_names": ["박성우"],
        "is_joint_ownership": False,
        "owner_shares": {"박성우": "1/1"},
    }
    with pytest.raises(TypeError):
        result.registry_fields["owner_names"] = ["변조"]


def test_build_judgment_input_rejects_missing_or_unknown_inputs():
    with pytest.raises(ValueError, match="owner_shares"):
        build_judgment_input(
            _judgment_snapshot(remove_registry=("owner_shares",)),
            judgment_ids=("J03",),
        )
    with pytest.raises(ValueError, match="알 수 없는 judgment_id"):
        build_judgment_input(_judgment_snapshot(), judgment_ids=("J13",))
    with pytest.raises(ValueError, match="중복"):
        build_judgment_input(_judgment_snapshot(), judgment_ids=("J01", "J01"))


def test_judgment_input_direct_validation_requires_confirmed_matching_fields():
    judgment_input = build_judgment_input(_judgment_snapshot(), judgment_ids=("J03",))
    payload = judgment_input.model_dump()
    payload["registry_fields"]["owner_shares"]["verification_status"] = "unverified"
    with pytest.raises(ValidationError, match="확인 완료"):
        JudgmentInput.model_validate(payload)

    payload = judgment_input.model_dump()
    payload["registry_fields"]["owner_shares"]["field_name"] = "owner_names"
    with pytest.raises(ValidationError, match="field_name"):
        JudgmentInput.model_validate(payload)


def test_judgment_known_fields_enforce_types_and_corrections_accept_share_map():
    fields = _registry_fields()
    fields["owner_shares"] = _field("owner_shares", ["박성우:1/1"])
    with pytest.raises(ValidationError, match="owner_shares"):
        DocumentExtraction(
            document_id="D1",
            document_type=DocumentType.REGISTRY,
            fields=fields,
        )
    correction = FieldCorrection(
        document_type=DocumentType.REGISTRY,
        field_name="owner_shares",
        corrected_value={"박성우": "1/1"},
    )
    assert correction.corrected_value == {"박성우": "1/1"}


def test_contract_id_uses_positive_backend_integer_identity():
    with pytest.raises(ValidationError):
        _snapshot(contract_id=0)
    with pytest.raises(ValidationError):
        _snapshot(contract_id="CT-1")
    with pytest.raises(ValidationError):
        _snapshot(contract_id="1")
    with pytest.raises(ValidationError):
        _snapshot(contract_id=True)
    assert _snapshot(contract_id=1, case_id="CASE-001").case_id == "CASE-001"


def test_snapshot_rejects_unverified_fields():
    with pytest.raises(ValidationError, match="확인 완료"):
        _snapshot(status=VerificationStatus.UNVERIFIED)


def test_snapshot_is_frozen():
    snapshot = _snapshot()
    with pytest.raises(ValidationError):
        snapshot.contract_id = 2
    with pytest.raises((TypeError, ValidationError)):
        snapshot.confirmed_fields.contract["landlord_name"] = _field()
    with pytest.raises((TypeError, ValidationError)):
        snapshot.confirmed_fields.contract["landlord_name"].extracted_value = "변조"
    with pytest.raises(TypeError):
        snapshot.confirmed_fields.registry["owner_names"].extracted_value.append("변조")
    with pytest.raises(ValidationError):
        snapshot.contract_context.deposit_paid = True


def test_snapshot_serialization_round_trip():
    snapshot = _snapshot(case_id="CASE-001")
    restored = InputSnapshot.model_validate_json(snapshot.model_dump_json())
    assert restored == snapshot


# --- RuleResult / AnalysisRunResult ---

def _rule_result(**overrides) -> RuleResult:
    payload = {
        "rule_id": "R01",
        "rule_name": "임대인=등기 소유자 이름 일치",
        "status": "불일치",
        "urgency": "즉시 확인",
        "reason": "이름이 다릅니다.",
        "limitations": "사기·위법 판단 아님.",
    }
    payload.update(overrides)
    payload.setdefault(
        "result_type",
        "fact_flag" if payload["rule_id"] in {"R03", "R04", "R05", "R07", "R10"} else "judgment",
    )
    payload.setdefault(
        "triggers_actions",
        payload["status"] not in {"일치", "명확", "적용 제외"},
    )
    return RuleResult(**payload)


def test_result_type_accepts_exactly_two_values():
    assert _rule_result(result_type="judgment").result_type is ResultType.JUDGMENT
    assert _rule_result(rule_id="R03", status="적용 제외").result_type is ResultType.FACT_FLAG
    with pytest.raises(ValidationError):
        _rule_result(result_type="action_trigger")


@pytest.mark.parametrize(
    ("rule_id", "expected"),
    [
        ("R01", ResultType.JUDGMENT),
        ("R02", ResultType.JUDGMENT),
        ("R03", ResultType.FACT_FLAG),
        ("R04", ResultType.FACT_FLAG),
        ("R05", ResultType.FACT_FLAG),
        ("R06", ResultType.JUDGMENT),
        ("R07", ResultType.FACT_FLAG),
        ("R08", ResultType.JUDGMENT),
        ("R09", ResultType.JUDGMENT),
        ("R10", ResultType.FACT_FLAG),
    ],
)
def test_rule_result_enforces_result_type_mapping(rule_id, expected):
    statuses = {
        "R01": "일치",
        "R02": "일치",
        "R03": "적용 제외",
        "R04": "적용 제외",
        "R05": "적용 제외",
        "R06": "일치",
        "R07": "확인 필요",
        "R08": "명확",
        "R09": "명확",
        "R10": "명확",
    }
    assert _rule_result(rule_id=rule_id, status=statuses[rule_id]).result_type is expected
    wrong = ResultType.FACT_FLAG if expected is ResultType.JUDGMENT else ResultType.JUDGMENT
    with pytest.raises(ValidationError, match="result_type"):
        _rule_result(rule_id=rule_id, status=statuses[rule_id], result_type=wrong)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("일치", False),
        ("명확", False),
        ("적용 제외", False),
        ("불일치", True),
        ("불명확", True),
        ("미기재", True),
        ("상충 가능", True),
        ("확인 필요", True),
        ("확인 불가", True),
    ],
)
def test_rule_result_enforces_action_trigger_by_status(status, expected):
    result = _rule_result(
        rule_id="R99",
        status=status,
        result_type="judgment",
        triggers_actions=expected,
    )
    assert result.triggers_actions is expected
    with pytest.raises(ValidationError, match="triggers_actions"):
        _rule_result(
            rule_id="R99",
            status=status,
            result_type="judgment",
            triggers_actions=not expected,
        )


def test_rule_result_serialization_round_trip_includes_classification():
    result = _rule_result()
    restored = RuleResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.model_dump()["result_type"] is ResultType.JUDGMENT
    assert restored.model_dump()["triggers_actions"] is True


def test_rule_result_rejects_unknown_status():
    with pytest.raises(ValidationError):
        _rule_result(status="안전")
    with pytest.raises(ValidationError):
        _rule_result(status="위험")


def test_rule_result_rejects_unknown_urgency():
    with pytest.raises(ValidationError):
        _rule_result(urgency="긴급")


def test_rule_result_rejects_status_not_allowed_for_rule():
    with pytest.raises(ValidationError, match="R01"):
        _rule_result(rule_id="R01", status="명확")
    assert _rule_result(rule_id="R01", status="일치").status.value == "일치"


def _complete_results() -> list[RuleResult]:
    statuses = {
        "R01": "일치",
        "R02": "일치",
        "R03": "적용 제외",
        "R04": "적용 제외",
        "R05": "적용 제외",
        "R06": "일치",
        "R07": "확인 필요",
        "R08": "명확",
        "R09": "명확",
        "R10": "명확",
    }
    return [
        _rule_result(rule_id=rule_id, status=status)
        for rule_id, status in statuses.items()
    ]


def _judgment_result(
    judgment_id: str = "J01",
    status: str = "일치",
    urgency: str | None = None,
    **overrides,
) -> JudgmentResult:
    trigger = status not in {"일치", "명확", "적용 제외"}
    payload = {
        "judgment_id": judgment_id,
        "judgment_name": f"{judgment_id} 판정",
        "status": status,
        "urgency": urgency or ("분석 불가" if status == "확인 불가" else "참고"),
        "triggers_actions": trigger,
        "reason": "판정 근거입니다.",
        "limitations": "이 결과만으로 법률 결론을 내리지 않습니다.",
    }
    payload.update(overrides)
    return JudgmentResult(**payload)


def _complete_judgments() -> list[JudgmentResult]:
    statuses = {
        "J01": "일치",
        "J02": "일치",
        "J03": "적용 제외",
        "J04": "적용 제외",
        "J05": "일치",
        "J06": "명확",
        "J07": "일치",
        "J08": "일치",
        "J09": "명확",
        "J10": "명확",
        "J11": "명확",
        "J12": "명확",
    }
    return [
        _judgment_result(judgment_id=judgment_id, status=status)
        for judgment_id, status in statuses.items()
    ]


@pytest.mark.parametrize(
    ("judgment_id", "allowed", "rejected"),
    [
        ("J01", "일치", "명확"),
        ("J02", "불일치", "미기재"),
        ("J03", "적용 제외", "일치"),
        ("J04", "확인 필요", "불일치"),
        ("J05", "확인 불가", "명확"),
        ("J06", "미기재", "불일치"),
        ("J07", "불일치", "불명확"),
        ("J08", "미기재", "확인 불가"),
        ("J09", "불명확", "일치"),
        ("J10", "불명확", "불일치"),
        ("J11", "미기재", "적용 제외"),
        ("J12", "상충 가능", "미기재"),
    ],
)
def test_judgment_result_enforces_allowed_statuses(judgment_id, allowed, rejected):
    assert _judgment_result(judgment_id, allowed).status.value == allowed
    with pytest.raises(ValidationError, match=judgment_id):
        _judgment_result(judgment_id, rejected)


def test_judgment_result_enforces_action_trigger_and_unanalyzable_urgency():
    assert _judgment_result("J01", "일치").triggers_actions is False
    assert _judgment_result("J01", "불일치").triggers_actions is True
    with pytest.raises(ValidationError, match="triggers_actions"):
        _judgment_result("J01", "불일치", triggers_actions=False)
    cannot_check = _judgment_result("J01", "확인 불가")
    assert cannot_check.urgency is Urgency.NOT_ANALYZABLE
    with pytest.raises(ValidationError, match="분석 불가"):
        _judgment_result("J01", "확인 불가", urgency="즉시 확인")


def test_analysis_run_rejects_duplicate_rule_ids_and_id_confusion():
    with pytest.raises(ValidationError):
        AnalysisRunResult(
            analysis_run_id="RUN-1",
            input_snapshot_id="SNAP-1",
            contract_id=1,
            results=[],
        )
    with pytest.raises(ValidationError):
        AnalysisRunResult(
            analysis_run_id="RUN-1",
            input_snapshot_id="SNAP-1",
            contract_id=1,
            results=_complete_results()[:-1] + [_rule_result(rule_id="R09", status="명확")],
        )
    with pytest.raises(ValidationError):
        AnalysisRunResult(
            analysis_run_id="RUN-1",
            input_snapshot_id="SNAP-1",
            contract_id=1,
            results=list(reversed(_complete_results())),
        )
    complete = AnalysisRunResult(
        analysis_run_id="RUN-1",
        input_snapshot_id="SNAP-1",
        contract_id=1,
        case_id="CASE-001",
        results=_complete_results(),
    )
    assert [result.rule_id for result in complete.results] == [f"R{i:02d}" for i in range(1, 11)]
    assert complete.judgments == []


def test_analysis_run_accepts_empty_or_complete_judgments_only():
    base = {
        "analysis_run_id": "RUN-1",
        "input_snapshot_id": "SNAP-1",
        "contract_id": 1,
        "results": _complete_results(),
    }
    complete = AnalysisRunResult(**base, judgments=_complete_judgments())
    assert [item.judgment_id for item in complete.judgments] == [
        f"J{i:02d}" for i in range(1, 13)
    ]
    with pytest.raises(ValidationError, match="J01~J12"):
        AnalysisRunResult(**base, judgments=_complete_judgments()[:-1])
    with pytest.raises(ValidationError, match="J01~J12"):
        AnalysisRunResult(**base, judgments=list(reversed(_complete_judgments())))
    duplicate = _complete_judgments()
    duplicate[-1] = _judgment_result("J11", "명확")
    with pytest.raises(ValidationError, match="J01~J12"):
        AnalysisRunResult(**base, judgments=duplicate)


def test_contract_context_matches_backend_api_values():
    context = ContractContext(
        contract_id=1,
        contract_type="보증부 월세",
        contract_stage="계약금 입금 전",
        deposit_paid=False,
        signed=False,
    )
    assert context.contract_type.value == "보증부 월세"
    assert context.contract_stage.value == "계약금 입금 전"
    with pytest.raises(ValidationError):
        ContractContext(
            contract_id=1,
            contract_type="보증부월세",
            contract_stage="before_deposit",
            deposit_paid=False,
            signed=False,
        )

def test_snapshot_rejects_contract_context_id_mismatch():
    snapshot = _snapshot()
    payload = snapshot.model_dump()
    payload["contract_context"]["contract_id"] = 2
    with pytest.raises(ValidationError, match="contract_id"):
        InputSnapshot.model_validate(payload)


def test_generation_result_validates_analysis_and_official_sources():
    results = _complete_results()
    results[0] = results[0].model_copy(
        update={
            "evidence_sources": [
                OfficialSource(
                    source_id="SRC-1",
                    title="공식 자료",
                    institution="공공기관",
                )
            ]
        }
    )
    analysis = AnalysisRunResult(
        analysis_run_id="RUN-1",
        input_snapshot_id="SNAP-1",
        contract_id=1,
        results=results,
        judgments=_complete_judgments(),
    )
    analysis.judgments[0].evidence_sources.append(
        OfficialSource(
            source_id="SRC-J01",
            title="J01 공식 자료",
            institution="공공기관",
        )
    )
    generation = GenerationResult(
        analysis_run_id="RUN-1",
        prompt_version="v1",
        stage_guidance=StageGuidance(contract_context=_context()),
        items=(
            RuleGuidance(
                rule_id="R01",
                explanation="공식 자료를 확인하십시오.",
                source_ids=("SRC-1",),
                generation_method=GenerationMethod.TEMPLATE_FALLBACK,
                fallback_reason="provider_unavailable",
            ),
        ),
        judgment_items=(
            JudgmentGuidance(
                judgment_id="J01",
                explanation="계약 상대와 등기 소유자를 확인하십시오.",
                source_ids=("SRC-J01",),
                generation_method=GenerationMethod.TEMPLATE_FALLBACK,
                fallback_reason="provider_unavailable",
            ),
        ),
    )

    assert generation.schema_version == SCHEMA_VERSION
    assert validate_generation_result_for_analysis(analysis, generation) is generation

    missing_judgment_items = generation.model_dump()
    missing_judgment_items.pop("judgment_items")
    with pytest.raises(ValidationError, match="judgment_items"):
        GenerationResult.model_validate(missing_judgment_items)

    with pytest.raises(ValueError, match="analysis_run_id"):
        validate_generation_result_for_analysis(
            analysis,
            generation.model_copy(update={"analysis_run_id": "RUN-2"}),
        )
    with pytest.raises(ValueError, match="contract_id"):
        validate_generation_result_for_analysis(
            analysis,
            generation.model_copy(
                update={"stage_guidance": StageGuidance(contract_context=_context(2))}
            ),
        )
    with pytest.raises(ValueError, match="없는 rule_id"):
        validate_generation_result_for_analysis(
            analysis,
            generation.model_copy(
                update={
                    "items": (
                        generation.items[0].model_copy(update={"rule_id": "R99"}),
                    )
                }
            ),
        )
    with pytest.raises(ValueError, match="공식 근거"):
        validate_generation_result_for_analysis(
            analysis,
            generation.model_copy(
                update={
                    "items": (
                        generation.items[0].model_copy(
                            update={"source_ids": ("SRC-UNKNOWN",)}
                        ),
                    )
                }
            ),
        )
    with pytest.raises(ValueError, match="중복 judgment_id"):
        GenerationResult(
            analysis_run_id="RUN-1",
            prompt_version="v1",
            stage_guidance=StageGuidance(contract_context=_context()),
            items=(),
            judgment_items=(generation.judgment_items[0],) * 2,
        )
    with pytest.raises(ValueError, match="없는 judgment_id"):
        validate_generation_result_for_analysis(
            analysis.model_copy(update={"judgments": []}),
            generation,
        )
    with pytest.raises(ValueError, match="공식 근거"):
        validate_generation_result_for_analysis(
            analysis,
            generation.model_copy(
                update={
                    "judgment_items": (
                        generation.judgment_items[0].model_copy(
                            update={"source_ids": ("SRC-UNKNOWN",)}
                        ),
                    )
                }
            ),
        )


def test_judgment_guidance_enforces_id_and_generation_metadata():
    with pytest.raises(ValidationError, match="judgment_id"):
        JudgmentGuidance(
            judgment_id="R01",
            explanation="잘못된 ID 축입니다.",
            generation_method=GenerationMethod.TEMPLATE_FALLBACK,
            fallback_reason="provider_unavailable",
        )
    with pytest.raises(ValidationError, match="provider_model"):
        JudgmentGuidance(
            judgment_id="J01",
            explanation="provider 메타데이터가 부족합니다.",
            generation_method=GenerationMethod.PROVIDER,
        )
