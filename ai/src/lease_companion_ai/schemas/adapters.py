"""통합 스키마(unified) ↔ 기존 최소 MVP 코드 사이의 변환 계층.

기존 R01~R10 규칙 엔진(rules/minimum_mvp.run_rules)은 재작성하지 않는다.
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

    field_names = set(raw_fields) | set(REQUIRED_FIELDS_BY_TYPE[doc_type]) | set(
        CANONICAL_FIELD_TYPES_BY_DOCUMENT[doc_type]
    )
    fields: dict[str, ExtractedField] = {}
    for name in sorted(field_names):
        value = raw_fields.get(name)
        if isinstance(value, list) and not value:
            value = None
        if value is None:
            fields[name] = ExtractedField(
                field_name=name,
                confidence=Confidence.FAILED,
                failure_reason=_READ_FAILURE_REASON,
                issue_code=FieldIssueCode.UNREADABLE,
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


def apply_correction(field: ExtractedField, corrected_value: FieldValue) -> ExtractedField:
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
    return field.model_copy(update={"verification_status": VerificationStatus.CONFIRMED})


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
    label = "contract" if document.document_type is DocumentType.CONTRACT else "registry_record"
    return {
        "document_type": label,
        "fields": {
            name: field.extracted_value for name, field in document.fields.items()
        },
        "unconfirmed_fields": [
            name for name, field in document.fields.items()
            if field.extracted_value is None
        ],
        "warnings": list(document.warnings),
    }


def apply_correction_request(
    documents: dict[DocumentType, DocumentExtraction], request: CorrectionRequest
) -> dict[DocumentType, DocumentExtraction]:
    """CorrectionRequest를 문서별 추출 결과에 적용한 새 사본을 반환한다."""
    fields_by_type = {
        doc_type: dict(doc.fields) for doc_type, doc in documents.items()
    }
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


def analyze_snapshot(snapshot: InputSnapshot, *, analysis_run_id: str) -> AnalysisRunResult:
    """확인 완료 스냅샷으로 R01~R10과 J01~J12를 실행한다."""
    legacy_results = run_rules(
        rule_inputs(snapshot.confirmed_fields.contract),
        rule_inputs(snapshot.confirmed_fields.registry),
    )
    analysis = AnalysisRunResult(
        analysis_run_id=analysis_run_id,
        input_snapshot_id=snapshot.input_snapshot_id,
        contract_id=snapshot.contract_id,
        case_id=snapshot.case_id,
        results=[rule_result_from_legacy(result) for result in legacy_results],
        judgments=run_judgments(build_judgment_input(snapshot)),
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
