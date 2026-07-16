"""통합 런타임 스키마 v1 — AI·Backend·Frontend 공통 데이터 계약의 단일 원본.

근거: docs/decisions/2026-07-16-shared-pydantic-schema.md
- 이 모듈의 Pydantic 모델이 canonical runtime schema다. Backend는 import해 재사용한다.
- JSON Schema는 손으로 쓰지 않고 scripts/generate_unified_schemas.py 로 생성한다.
- J01~J12 확장은 필드 "추가"로만 진행한다. 기존 필드 이름·의미를 바꾸지 않는다(하위 호환).

식별자 구분(혼용 금지):
- contract_id        실제 사용자 계약 건
- case_id            CASE-001 같은 합성·평가 사례 (fixture/goldset 전용)
- document_id        업로드 문서 1건
- input_snapshot_id  사용자 확인 완료 입력의 불변 스냅샷
- analysis_run_id    분석 실행 1회
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0.0"
SchemaVersion = Literal["1.0.0"]

# 필드 값 타입 — R01~R10 입력이 쓰는 형태만 허용(str·int·bool·list[str]·null).
# dict 등 구조체 값은 거부한다. 새 값 형태가 필요하면 J 확장에서 타입을 "추가"한다.
class FrozenList(list):
    """JSON array 모양을 유지하는 불변 list."""

    def _immutable(self, *args, **kwargs):
        raise TypeError("불변 목록은 수정할 수 없습니다.")

    __setitem__ = __delitem__ = __iadd__ = __imul__ = _immutable
    append = clear = extend = insert = pop = remove = reverse = sort = _immutable


class FrozenDict(dict):
    """JSON object 모양을 유지하는 불변 dict."""

    def _immutable(self, *args, **kwargs):
        raise TypeError("불변 매핑은 수정할 수 없습니다.")

    __setitem__ = __delitem__ = __ior__ = _immutable
    clear = pop = popitem = setdefault = update = _immutable


FrozenStringList = Annotated[list[str], AfterValidator(FrozenList)]
FieldValue = Union[str, int, bool, FrozenStringList, None]
ContractId = Annotated[int, Field(gt=0, strict=True)]


class Confidence(str, Enum):
    """추출 신뢰도 3등급. 숫자 confidence는 허용하지 않는다(ADR 확정)."""

    EXTRACTED = "추출됨"
    UNCERTAIN = "불확실"
    FAILED = "실패"


class VerificationStatus(str, Enum):
    """사용자 확인 상태 — 기존 minimum-mvp-extraction-v1 어휘 재사용."""

    UNVERIFIED = "unverified"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"


class DocumentType(str, Enum):
    CONTRACT = "contract"
    REGISTRY = "registry"


class RuleStatus(str, Enum):
    """공통 결과 상태 9개 — 루트 AGENTS.md 확정 어휘. 새 상태를 만들지 않는다."""

    MATCH = "일치"
    MISMATCH = "불일치"
    CLEAR = "명확"
    UNCLEAR = "불명확"
    NOT_STATED = "미기재"
    POSSIBLE_CONFLICT = "상충 가능"
    CHECK_NEEDED = "확인 필요"
    CANNOT_CHECK = "확인 불가"
    NOT_APPLICABLE = "적용 제외"


class Urgency(str, Enum):
    """시급도 5개 — 루트 AGENTS.md 확정 어휘. 판정 상태와 별도 축."""

    IMMEDIATE = "즉시 확인"
    BEFORE_CONTRACT = "계약 전 확인"
    AFTER_CONTRACT = "계약 직후 조치"
    REFERENCE = "참고"
    NOT_ANALYZABLE = "분석 불가"


class ContractType(str, Enum):
    JEONSE = "전세"
    DEPOSIT_MONTHLY = "보증부 월세"
    MONTHLY = "일반 월세"


class ContractStage(str, Enum):
    BEFORE_DEPOSIT = "계약금 입금 전"
    BEFORE_SIGNING = "서명 전"
    AFTER_CONTRACT = "계약 직후"


# 현행 R01~R10이 실제로 사용하는 canonical 필드 — 키는 추출 결과에 항상 존재해야 한다.
REQUIRED_CONTRACT_FIELDS: frozenset[str] = frozenset(
    {
        "landlord_name",
        "property_address",
        "account_holder",
        "deposit_return_condition",
        "repair_responsibility",
        "rights_change_clause_present",
    }
)
REQUIRED_REGISTRY_FIELDS: frozenset[str] = frozenset(
    {
        "owner_names",
        "property_address",
        "issue_date",
        "mortgage_present",
        "seizure_present",
        "provisional_seizure_present",
        "trust_present",
    }
)
REQUIRED_FIELDS_BY_TYPE: dict[DocumentType, frozenset[str]] = {
    DocumentType.CONTRACT: REQUIRED_CONTRACT_FIELDS,
    DocumentType.REGISTRY: REQUIRED_REGISTRY_FIELDS,
}

# R01~R10 canonical 필드의 값 타입. null은 판독 실패를 표현하므로 모두 허용한다.
# bool은 int의 하위 타입이므로 isinstance 대신 type(value) is expected_type으로 검사한다.
R_FIELD_TYPES_BY_DOCUMENT: dict[DocumentType, dict[str, type]] = {
    DocumentType.CONTRACT: {
        "landlord_name": str,
        "property_address": str,
        "account_holder": str,
        "deposit_return_condition": str,
        "repair_responsibility": str,
        "rights_change_clause_present": bool,
    },
    DocumentType.REGISTRY: {
        "owner_names": list,
        "property_address": str,
        "issue_date": str,
        "mortgage_present": bool,
        "seizure_present": bool,
        "provisional_seizure_present": bool,
        "trust_present": bool,
    },
}

ALLOWED_RULE_STATUSES: dict[str, frozenset[RuleStatus]] = {
    "R01": frozenset({RuleStatus.MATCH, RuleStatus.MISMATCH, RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}),
    "R02": frozenset({RuleStatus.MATCH, RuleStatus.MISMATCH, RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}),
    "R03": frozenset({RuleStatus.CHECK_NEEDED, RuleStatus.NOT_APPLICABLE, RuleStatus.CANNOT_CHECK}),
    "R04": frozenset({RuleStatus.CHECK_NEEDED, RuleStatus.NOT_APPLICABLE, RuleStatus.CANNOT_CHECK}),
    "R05": frozenset({RuleStatus.CHECK_NEEDED, RuleStatus.NOT_APPLICABLE, RuleStatus.CANNOT_CHECK}),
    "R06": frozenset({RuleStatus.MATCH, RuleStatus.MISMATCH, RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}),
    "R07": frozenset({RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}),
    "R08": frozenset({RuleStatus.CLEAR, RuleStatus.UNCLEAR, RuleStatus.NOT_STATED, RuleStatus.CHECK_NEEDED}),
    "R09": frozenset({RuleStatus.CLEAR, RuleStatus.UNCLEAR, RuleStatus.NOT_STATED, RuleStatus.CHECK_NEEDED}),
    "R10": frozenset({RuleStatus.CLEAR, RuleStatus.NOT_STATED, RuleStatus.CANNOT_CHECK}),
}


class SourceEvidence(BaseModel):
    """원문 증거. page/text 키는 항상 존재하고 값은 둘 다 null 허용(ADR 확정)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page: int | None = None
    text: str | None = None


class ExtractedField(BaseModel):
    """추출 필드 1개.

    - extracted_value: AI 최초 추출값. 사용자 수정으로 덮어쓰지 않는다(불변 보존).
    - user_corrected_value: 사용자 수정값(user_corrected_value 규약).
    - 규칙 입력(effective_value): user_corrected_value → normalized_value → extracted_value.
    - 판독 실패는 값 null + failure_reason 으로 표현한다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_name: str = Field(min_length=1)
    extracted_value: FieldValue = None
    normalized_value: FieldValue = None
    user_corrected_value: FieldValue = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: Confidence
    source_evidence: SourceEvidence = Field(default_factory=SourceEvidence)
    failure_reason: str | None = None

    @field_validator("extracted_value", "normalized_value", "user_corrected_value")
    @classmethod
    def _no_empty_list(cls, value: FieldValue) -> FieldValue:
        # 빈 목록 금지: "없음을 읽음"은 값으로, "못 읽음"은 null+failure_reason으로 표현한다.
        # (owner_names 등 list 필드는 non-null이면 항목 1개 이상 — ADR 권장 기준)
        if isinstance(value, list):
            if not value:
                raise ValueError("빈 목록은 허용하지 않습니다. 판독 실패는 null과 failure_reason으로 표현하세요.")
            if not all(isinstance(item, str) and item for item in value):
                raise ValueError("목록 값은 비어 있지 않은 문자열이어야 합니다.")
        return value

    @model_validator(mode="after")
    def _consistency(self) -> "ExtractedField":
        if self.confidence is Confidence.EXTRACTED and self.extracted_value is None:
            raise ValueError("confidence=추출됨 인 필드는 extracted_value가 null일 수 없습니다.")
        if self.confidence is Confidence.FAILED and self.failure_reason is None:
            raise ValueError("confidence=실패 인 필드는 failure_reason이 필요합니다.")
        if self.verification_status is VerificationStatus.CORRECTED and self.user_corrected_value is None:
            raise ValueError("verification_status=corrected 인 필드는 user_corrected_value가 필요합니다.")
        return self

    @property
    def effective_value(self) -> FieldValue:
        """규칙 엔진 입력값. 수정값 → 정규화값 → 최초 추출값 순."""
        if self.user_corrected_value is not None:
            return self.user_corrected_value
        if self.normalized_value is not None:
            return self.normalized_value
        return self.extracted_value


def _validate_fields_map(
    fields: dict[str, ExtractedField], document_type: DocumentType
) -> dict[str, ExtractedField]:
    for key, item in fields.items():
        if key != item.field_name:
            raise ValueError(f"fields 키 '{key}'와 field_name '{item.field_name}'이 다릅니다.")
    missing = REQUIRED_FIELDS_BY_TYPE[document_type] - fields.keys()
    if missing:
        raise ValueError(
            f"{document_type.value} 추출 결과에 필수 키가 없습니다: {sorted(missing)} "
            "(값을 못 읽어도 키는 null로 존재해야 합니다)"
        )
    for field_name, expected_type in R_FIELD_TYPES_BY_DOCUMENT[document_type].items():
        item = fields[field_name]
        for value_name in ("extracted_value", "normalized_value", "user_corrected_value"):
            value = getattr(item, value_name)
            if value is None:
                continue
            valid = (
                isinstance(value, list)
                if expected_type is list
                else type(value) is expected_type
            )
            if not valid:
                expected_name = "list[str]" if expected_type is list else expected_type.__name__
                raise ValueError(
                    f"{document_type.value}.{field_name}.{value_name}는 "
                    f"{expected_name} 또는 null이어야 합니다."
                )
    return fields


class DocumentExtraction(BaseModel):
    """문서 1건의 추출 결과. R01~R10 필수 키는 값이 null이어도 항상 존재한다."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = SCHEMA_VERSION
    document_id: str = Field(min_length=1)
    document_type: DocumentType
    fields: dict[str, ExtractedField]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_fields(self) -> "DocumentExtraction":
        _validate_fields_map(self.fields, self.document_type)
        return self


class SnapshotFields(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract: Annotated[dict[str, ExtractedField], AfterValidator(FrozenDict)]
    registry: Annotated[dict[str, ExtractedField], AfterValidator(FrozenDict)]

    @model_validator(mode="after")
    def _check(self) -> "SnapshotFields":
        _validate_fields_map(self.contract, DocumentType.CONTRACT)
        _validate_fields_map(self.registry, DocumentType.REGISTRY)
        return self


class InputSnapshot(BaseModel):
    """사용자가 확인을 완료한 시점 입력의 불변 사본. 분석 실행의 입력 단위."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    input_snapshot_id: str = Field(min_length=1)
    contract_id: ContractId
    case_id: str | None = None  # 합성·평가 fixture 연결 전용. 실계약 식별자가 아니다.
    confirmed_fields: SnapshotFields
    confirmed_at: datetime

    @model_validator(mode="after")
    def _check(self) -> "InputSnapshot":
        for doc_fields in (self.confirmed_fields.contract, self.confirmed_fields.registry):
            for item in doc_fields.values():
                if item.verification_status is VerificationStatus.UNVERIFIED:
                    raise ValueError(
                        f"스냅샷에는 확인 완료(confirmed/corrected) 필드만 담을 수 있습니다: {item.field_name}"
                    )
        return self


class OfficialSource(BaseModel):
    """공식 근거 참조(정적 카탈로그 항목). 원문 증거(SourceEvidence)와 구분."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    title: str
    institution: str
    # 현행 source_inventory.csv에 요약이 비어 있는 항목이 있어 null 허용.
    summary: str | None = None
    source_url: str | None = None


class RuleResult(BaseModel):
    """규칙 1개의 최종 판정. status·urgency는 확정 어휘만 사용(새 상태 금지)."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(pattern=r"^R\d{2}$")
    rule_name: str
    judgment_id: str | None = None
    status: RuleStatus
    urgency: Urgency
    reason: str
    question: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    evidence_sources: list[OfficialSource] = Field(default_factory=list)
    limitations: str
    completed: bool = False

    @model_validator(mode="after")
    def _check_allowed_status(self) -> "RuleResult":
        allowed = ALLOWED_RULE_STATUSES.get(self.rule_id)
        if allowed is not None and self.status not in allowed:
            values = ", ".join(sorted(status.value for status in allowed))
            raise ValueError(f"{self.rule_id}에서 허용되지 않는 status입니다: {self.status.value} (허용: {values})")
        return self


class AnalysisRunResult(BaseModel):
    """분석 실행 1회의 R01~R10 결과 묶음."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = SCHEMA_VERSION
    analysis_run_id: str = Field(min_length=1)
    input_snapshot_id: str = Field(min_length=1)
    contract_id: ContractId
    case_id: str | None = None
    results: list[RuleResult] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def _check(self) -> "AnalysisRunResult":
        rule_ids = [result.rule_id for result in self.results]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("results에 중복 rule_id가 있습니다.")
        expected = [f"R{index:02d}" for index in range(1, 11)]
        if rule_ids != expected:
            raise ValueError("results에는 R01~R10이 순서대로 각각 정확히 1개씩 있어야 합니다.")
        return self


class ContractContext(BaseModel):
    """계약 상황 입력 — 2026-07-16 팀 확정 필드."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = SCHEMA_VERSION
    contract_id: ContractId
    contract_type: ContractType
    contract_stage: ContractStage
    deposit_paid: bool
    signed: bool
    move_in_date: date | None = None
    balance_payment_date: date | None = None
    is_proxy_contract: bool | None = None  # null = 모름


class FieldCorrection(BaseModel):
    """사용자 수정 요청 1건 — corrected_value는 null 불가(수정 취소는 별도 흐름)."""

    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    field_name: str = Field(min_length=1)
    corrected_value: str | int | bool | list[str]

    @field_validator("corrected_value")
    @classmethod
    def _no_empty_list(cls, value: str | int | bool | list[str]) -> str | int | bool | list[str]:
        if isinstance(value, list) and not value:
            raise ValueError("빈 목록으로 수정할 수 없습니다.")
        return value

    @model_validator(mode="after")
    def _check_r_field_type(self) -> "FieldCorrection":
        expected_type = R_FIELD_TYPES_BY_DOCUMENT[self.document_type].get(self.field_name)
        if expected_type is None:
            return self
        valid = (
            isinstance(self.corrected_value, list)
            if expected_type is list
            else type(self.corrected_value) is expected_type
        )
        if not valid:
            expected_name = "list[str]" if expected_type is list else expected_type.__name__
            raise ValueError(
                f"{self.document_type.value}.{self.field_name}.corrected_value는 {expected_name}이어야 합니다."
            )
        return self


class CorrectionRequest(BaseModel):
    """추출값 확인·수정 화면 → Backend 수정 요청."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = SCHEMA_VERSION
    contract_id: ContractId
    corrections: list[FieldCorrection] = Field(min_length=1)
