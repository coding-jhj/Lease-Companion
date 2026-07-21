"""통합 스키마(unified) ↔ 기존 최소 MVP 코드 사이의 변환 계층.

R01~R24 규칙 엔진(rules/minimum_mvp.run_rules)을 canonical 결과로 변환한다.
흐름: 기존 추출 dict → DocumentExtraction → (사용자 확인·수정) → InputSnapshot
      → effective value 평면 dict → 기존 run_rules() → RuleResult(unified).

정규화(normalize_name/address)는 기존대로 규칙 엔진 내부에서 수행하므로,
legacy 변환 시 normalized_value는 채우지 않는다(effective_value가 extracted로 폴백).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from lease_companion_ai.rules.minimum_mvp import run_rules
from lease_companion_ai.rules.judgments import run_judgments
from lease_companion_ai.schemas import minimum_mvp as legacy
from lease_companion_ai.schemas.unified import (
    ACTION_TRIGGER_STATUSES,
    ALLOWED_RULE_STATUSES,
    CANONICAL_FIELD_TYPES_BY_DOCUMENT,
    REQUIRED_FIELDS_BY_TYPE,
    RESULT_TYPE_BY_RULE_ID,
    AnalysisRunResult,
    ClassificationResult,
    Confidence,
    ContractContext,
    CorrectionRequest,
    DocumentExtraction,
    DocumentType,
    ExtractedField,
    FieldValue,
    FieldIssueCode,
    InputSnapshot,
    OfficialSource,
    RuleResult,
    RuleStatus,
    SnapshotFields,
    Urgency,
    VerificationStatus,
    build_judgment_input,
)

_READ_FAILURE_REASON = "문서에서 값을 읽지 못했습니다."
_DIRECT_CONFIRMATION_REASONS = {
    "estimated_housing_value": "계약서 자동추출값이 아닙니다. 주택가치 자료와 기준일을 직접 확인해 입력하세요.",
    "violation_building": "계약서 자동추출값이 아닙니다. 최신 건축물대장의 위반건축물 표시를 확인하세요.",
    "guarantee_eligibility_confirmed": "계약서 자동추출값이 아닙니다. 보증기관의 현재 가입 요건을 직접 확인하세요.",
    "lessor_sublease_authority_confirmed": "계약서 문구만으로 확정할 수 없습니다. 소유권 또는 전대 동의 서류를 확인하세요.",
    "senior_claim_amount": "등기사항증명서의 권리 종류·금액·순위만으로 자동 확정하지 않습니다. 채권최고액과 실제 채무 자료를 직접 확인하세요.",
}

# 기존 코드의 document_type 라벨(pipelines._structure의 "registry_record" 등) → 통합 enum.
_LEGACY_TYPE_MAP = {
    "contract": DocumentType.CONTRACT,
    "registry": DocumentType.REGISTRY,
    "registry_record": DocumentType.REGISTRY,
}


def document_from_legacy(
    legacy_doc: dict[str, Any], *, document_id: str
) -> DocumentExtraction:
    """기존 추출 결과(dict: document_type/fields/unconfirmed_fields/warnings) → DocumentExtraction.

    - 값이 None인 필드: confidence=실패 + failure_reason (판독 실패 표현).
    - 빈 목록 값: null로 정규화(빈 목록 금지 규칙).
    - R 필수 키가 legacy에 아예 없으면 null 실패 필드로 채워 키를 항상 존재시킨다.
    """
    doc_type = _LEGACY_TYPE_MAP[legacy_doc["document_type"]]
    raw_fields: dict[str, Any] = dict(legacy_doc.get("fields") or {})
    no_proxy_indicated = (
        doc_type is DocumentType.CONTRACT
        and not raw_fields.get("agent_name")
        and not raw_fields.get("agent_relationship")
        and not raw_fields.get("proxy_authority_documents")
    )

    field_names = (
        set(raw_fields)
        | set(REQUIRED_FIELDS_BY_TYPE[doc_type])
        | set(CANONICAL_FIELD_TYPES_BY_DOCUMENT[doc_type])
    )
    fields: dict[str, ExtractedField] = {}
    for name in sorted(field_names):
        value = raw_fields.get(name)
        # 빈 컬렉션(리스트·매핑)은 ExtractedField가 금지 — "없음"은 null로 표현한다.
        # (예: Gemini가 owner_shares를 빈 객체 {}로 반환하는 경우)
        if isinstance(value, (list, dict)) and not value:
            value = None
        if value is None:
            if no_proxy_indicated and name in {
                "agent_name",
                "agent_relationship",
                "proxy_authority_documents",
            }:
                fields[name] = ExtractedField(
                    field_name=name,
                    confidence=Confidence.UNCERTAIN,
                    failure_reason="문서에 대리인 계약 표시가 없어 적용되지 않습니다.",
                    issue_code=FieldIssueCode.NOT_APPLICABLE,
                )
                continue
            if (
                doc_type is DocumentType.CONTRACT
                and name == "management_fee"
                and raw_fields.get("management_fee_present") is True
                and raw_fields.get("management_fee_items")
            ):
                fields[name] = ExtractedField(
                    field_name=name,
                    confidence=Confidence.UNCERTAIN,
                    failure_reason="사용량·세대수 등에 따라 산정되어 문서에 고정 관리비 금액이 없습니다.",
                    issue_code=FieldIssueCode.NOT_STATED,
                )
                continue
            # 예금주는 계좌번호·은행명만 적는 계약서가 흔하다. null을 "판독 실패"가 아니라
            # "미기재"로 표시해 사용자가 추출 오류로 오해하지 않게 한다(계좌번호·은행명은 별도 필드).
            if name == "account_holder" and doc_type is DocumentType.CONTRACT:
                fields[name] = ExtractedField(
                    field_name=name,
                    confidence=Confidence.UNCERTAIN,
                    failure_reason="문서에 예금주가 기재되어 있지 않습니다. (미기재)",
                    issue_code=FieldIssueCode.NOT_STATED,
                )
            else:
                direct_confirmation_reason = _DIRECT_CONFIRMATION_REASONS.get(name)
                fields[name] = ExtractedField(
                    field_name=name,
                    confidence=Confidence.FAILED,
                    failure_reason=direct_confirmation_reason or _READ_FAILURE_REASON,
                    issue_code=(
                        FieldIssueCode.NOT_STATED
                        if direct_confirmation_reason
                        else FieldIssueCode.UNREADABLE
                    ),
                )
        else:
            fields[name] = ExtractedField(
                field_name=name,
                extracted_value=value,
                confidence=Confidence.EXTRACTED,
            )
    return DocumentExtraction(
        document_id=document_id,
        document_type=doc_type,
        fields=fields,
        warnings=list(legacy_doc.get("warnings") or []),
    )


def apply_correction(
    field: ExtractedField, corrected_value: FieldValue
) -> ExtractedField:
    """사용자 수정 적용 — extracted_value는 절대 덮어쓰지 않고 새 객체를 반환한다."""
    updated = field.model_copy(
        update={
            "user_corrected_value": corrected_value,
            "verification_status": VerificationStatus.CORRECTED,
            "issue_code": None if corrected_value is not None else field.issue_code,
        }
    )
    # model_copy는 validator를 다시 돌리지 않는다 — 수정값도 스키마 규칙을 지키도록 재검증.
    return ExtractedField.model_validate(updated.model_dump())


def confirm_field(field: ExtractedField) -> ExtractedField:
    """수정 없이 값 확인 완료 표시. 이미 corrected인 필드는 그대로 둔다."""
    if field.verification_status is VerificationStatus.CORRECTED:
        return field
    return field.model_copy(
        update={"verification_status": VerificationStatus.CONFIRMED}
    )


def confirm_document(document: DocumentExtraction) -> DocumentExtraction:
    """사용자가 문서 전체를 대조·확인했다는 명시적 동작을 새 객체로 반영한다."""
    payload = document.model_dump()
    payload["fields"] = {
        name: confirm_field(field).model_dump()
        for name, field in document.fields.items()
    }
    return DocumentExtraction.model_validate(payload)


def document_to_legacy(document: DocumentExtraction) -> dict[str, Any]:
    """통합 추출 결과를 기존 minimum MVP API 응답 모양으로 변환한다."""
    label = (
        "contract"
        if document.document_type is DocumentType.CONTRACT
        else "registry_record"
    )
    return {
        "document_type": label,
        "fields": {
            name: field.extracted_value for name, field in document.fields.items()
        },
        "unconfirmed_fields": [
            name
            for name, field in document.fields.items()
            if field.extracted_value is None
        ],
        "warnings": list(document.warnings),
    }


def apply_correction_request(
    documents: dict[DocumentType, DocumentExtraction], request: CorrectionRequest
) -> dict[DocumentType, DocumentExtraction]:
    """CorrectionRequest를 문서별 추출 결과에 적용한 새 사본을 반환한다."""
    fields_by_type = {doc_type: dict(doc.fields) for doc_type, doc in documents.items()}
    for correction in request.corrections:
        doc_fields = fields_by_type.get(correction.document_type)
        if doc_fields is None or correction.field_name not in doc_fields:
            raise KeyError(
                f"수정 대상 필드가 없습니다: {correction.document_type.value}.{correction.field_name}"
            )
        doc_fields[correction.field_name] = apply_correction(
            doc_fields[correction.field_name], correction.corrected_value
        )
    return {
        doc_type: doc.model_copy(update={"fields": fields_by_type[doc_type]})
        for doc_type, doc in documents.items()
    }


def build_snapshot(
    *,
    input_snapshot_id: str,
    contract_id: int,
    contract_context: ContractContext,
    contract_doc: DocumentExtraction,
    registry_doc: DocumentExtraction,
    confirmed_at: datetime,
    case_id: str | None = None,
) -> InputSnapshot:
    """확인 완료 스냅샷 생성. 미확인 필드는 자동 승인하지 않고 거부한다."""
    return InputSnapshot(
        input_snapshot_id=input_snapshot_id,
        contract_id=contract_id,
        case_id=case_id,
        contract_context=contract_context,
        confirmed_at=confirmed_at,
        confirmed_fields=SnapshotFields(
            contract=dict(contract_doc.fields),
            registry=dict(registry_doc.fields),
        ),
    )


def rule_inputs(fields: dict[str, ExtractedField]) -> dict[str, Any]:
    """기존 run_rules()가 이해하는 평면 dict — effective value 계산 지점."""
    return {name: field.effective_value for name, field in fields.items()}


def rule_result_from_legacy(result: legacy.RuleResult) -> RuleResult:
    """기존 dataclass RuleResult → 통합 RuleResult. 상태·시급도는 확정 어휘로 검증된다."""
    status = RuleStatus(result.status)
    return RuleResult(
        rule_id=result.rule_id,
        rule_name=result.rule_name,
        judgment_id=result.judgment_id,
        result_type=RESULT_TYPE_BY_RULE_ID[result.rule_id],
        triggers_actions=status in ACTION_TRIGGER_STATUSES,
        status=status,
        urgency=Urgency(result.urgency),
        reason=result.reason,
        question=result.question,
        recommended_actions=list(result.recommended_actions),
        evidence_sources=[
            OfficialSource(**source.to_dict()) for source in result.evidence_sources
        ],
        limitations=result.limitations,
        completed=result.completed,
    )


def analyze_snapshot(
    snapshot: InputSnapshot,
    *,
    analysis_run_id: str,
    classification_result: ClassificationResult | None = None,
) -> AnalysisRunResult:
    """확인 완료 스냅샷으로 R01~R24와 J01~J12를 실행한다."""
    contract_inputs = rule_inputs(snapshot.confirmed_fields.contract)
    contract_inputs["is_proxy_contract"] = snapshot.contract_context.is_proxy_contract
    legacy_results = run_rules(
        contract_inputs,
        rule_inputs(snapshot.confirmed_fields.registry),
    )
    analysis = AnalysisRunResult(
        analysis_run_id=analysis_run_id,
        input_snapshot_id=snapshot.input_snapshot_id,
        contract_id=snapshot.contract_id,
        case_id=snapshot.case_id,
        results=[rule_result_from_legacy(result) for result in legacy_results],
        judgments=run_judgments(
            build_judgment_input(
                snapshot,
                classification_result=classification_result,
            )
        ),
    )
    # 로컬 공식 원문 검색 실패는 규칙 분석 실패로 전파하지 않는다.
    try:
        from lease_companion_ai.rag.service import get_default_evidence_service

        return get_default_evidence_service().enrich(analysis)
    except (OSError, ValueError):
        return analysis


def allowed_statuses(rule_id: str) -> set[RuleStatus]:
    """규칙별 허용 상태 집합. 명세와의 일치는 contract test에서 검증한다."""
    try:
        return set(ALLOWED_RULE_STATUSES[rule_id])
    except KeyError as exc:
        raise KeyError(f"허용 상태가 정의되지 않은 규칙: {rule_id}") from exc
