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
from typing import Annotated, Literal, Mapping, Union

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

SchemaVersion = Literal["1.8.0", "1.9.0"]
SCHEMA_VERSION: SchemaVersion = "1.9.0"
GenerationPromptVersion = Literal["v1", "v2"]  # v1은 과거 저장 결과 읽기 호환용
GENERATION_PROMPT_VERSION: GenerationPromptVersion = "v2"

# 필드 값 타입 — 문서 추출·사용자 수정·판정 입력이 공유하는 wire 형태.
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
FrozenStringMap = Annotated[dict[str, str], AfterValidator(FrozenDict)]
FieldValue = Union[str, int, bool, FrozenStringList, FrozenStringMap, None]
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


class FieldIssueCode(str, Enum):
    """J 판정에서 null·모호 값의 의미를 자유문 대신 구조화한다."""

    NOT_STATED = "not_stated"
    UNREADABLE = "unreadable"
    AMBIGUOUS = "ambiguous"
    PARSE_FAILED = "parse_failed"
    NOT_APPLICABLE = "not_applicable"


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


class ResultType(str, Enum):
    """규칙 결과의 역할. 행동 활성화 여부와는 별도 축이다."""

    JUDGMENT = "judgment"
    FACT_FLAG = "fact_flag"


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


JUDGMENT_IDS: tuple[str, ...] = tuple(f"J{index:02d}" for index in range(1, 14))

# judgment id 정규식을 상수에서 만든다. 두 곳에 하드코딩하면 확장 시 어긋난다.
_JUDGMENT_ID_PATTERN: str = "^(?:" + "|".join(JUDGMENT_IDS) + ")$"

DEFAULT_JUDGMENT_URGENCY: dict[str, Urgency] = {
    "J01": Urgency.IMMEDIATE,
    "J02": Urgency.BEFORE_CONTRACT,
    "J03": Urgency.BEFORE_CONTRACT,
    "J04": Urgency.IMMEDIATE,
    "J05": Urgency.IMMEDIATE,
    "J06": Urgency.BEFORE_CONTRACT,
    "J07": Urgency.BEFORE_CONTRACT,
    "J08": Urgency.BEFORE_CONTRACT,
    "J09": Urgency.REFERENCE,
    "J10": Urgency.BEFORE_CONTRACT,
    "J11": Urgency.REFERENCE,
    "J12": Urgency.IMMEDIATE,
    "J13": Urgency.IMMEDIATE,
}


class ContractContext(BaseModel):
    """계약 상황 입력 — 스냅샷에 포함되는 불변 분석 입력."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    contract_id: ContractId
    contract_type: ContractType
    contract_stage: ContractStage
    deposit_paid: bool
    signed: bool
    move_in_date: date | None = None
    balance_payment_date: date | None = None
    is_proxy_contract: bool | None = None  # null = 모름


class JudgmentInputSpec(BaseModel):
    """판정 1개가 J 실행 경계에서 요구하는 canonical 입력 키."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_fields: tuple[str, ...] = ()
    registry_fields: tuple[str, ...] = ()
    context_fields: tuple[str, ...] = ()


JUDGMENT_INPUT_SPECS: dict[str, JudgmentInputSpec] = {
    "J01": JudgmentInputSpec(
        contract_fields=("landlord_name",),
        registry_fields=("owner_names",),
        context_fields=("is_proxy_contract",),
    ),
    "J02": JudgmentInputSpec(
        contract_fields=("property_address",),
        registry_fields=("property_address",),
    ),
    "J03": JudgmentInputSpec(
        registry_fields=("owner_names", "is_joint_ownership", "owner_shares"),
    ),
    "J04": JudgmentInputSpec(
        contract_fields=("agent_name", "agent_relationship", "proxy_authority_documents"),
        context_fields=("is_proxy_contract",),
    ),
    "J05": JudgmentInputSpec(
        contract_fields=("account_holder", "landlord_name"),
        registry_fields=("owner_names",),
        context_fields=("is_proxy_contract",),
    ),
    "J06": JudgmentInputSpec(
        contract_fields=("deposit", "monthly_rent", "contract_payment", "balance_payment"),
        context_fields=("contract_type",),
    ),
    "J07": JudgmentInputSpec(
        contract_fields=(
            "deposit",
            "deposit_korean_amount",
            "monthly_rent",
            "monthly_rent_korean_amount",
            "contract_payment",
            "contract_payment_korean_amount",
            "balance_payment",
            "balance_payment_korean_amount",
        ),
        context_fields=("contract_type",),
    ),
    "J08": JudgmentInputSpec(
        contract_fields=(
            "contract_payment_date",
            "balance_payment_date",
            "move_in_date",
            "start_date",
            "end_date",
        ),
        context_fields=("move_in_date", "balance_payment_date"),
    ),
    "J09": JudgmentInputSpec(
        contract_fields=("management_fee_present", "management_fee", "management_fee_items"),
    ),
    "J10": JudgmentInputSpec(
        contract_fields=("deposit_return_clause",),
    ),
    "J11": JudgmentInputSpec(
        contract_fields=("repair_responsibility_clause",),
    ),
    "J12": JudgmentInputSpec(
        contract_fields=("main_clauses", "special_clauses_present", "special_clauses"),
    ),
    "J13": JudgmentInputSpec(
        contract_fields=("special_clauses_present", "special_clauses"),
    ),
}


# 현행 R01~R10이 실제로 사용하는 canonical 필드 — 키는 추출 결과에 항상 존재해야 한다.
REQUIRED_CONTRACT_FIELDS: frozenset[str] = frozenset(
    {
        "landlord_name",
        "property_address",
        "account_holder",
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

# R 규칙 canonical 필드의 값 타입. null은 판독 실패·미입력을 표현하므로 모두 허용한다.
# bool은 int의 하위 타입이므로 isinstance 대신 type(value) is expected_type으로 검사한다.
R_FIELD_TYPES_BY_DOCUMENT: dict[DocumentType, dict[str, type]] = {
    DocumentType.CONTRACT: {
        "landlord_name": str,
        "property_address": str,
        "account_holder": str,
        "deposit_return_condition": str,
        "repair_responsibility": str,
        "rights_change_clause_present": bool,
        "estimated_housing_value": int,
        "building_use": str,
        "violation_building": bool,
        "guarantee_eligibility_confirmed": bool,
        "lessor_sublease_authority_confirmed": bool,
    },
    DocumentType.REGISTRY: {
        "owner_names": list,
        "property_address": str,
        "issue_date": str,
        "mortgage_present": bool,
        "seizure_present": bool,
        "provisional_seizure_present": bool,
        "trust_present": bool,
        "senior_claim_amount": int,
        "ground_right_present": bool,
    },
}

J_FIELD_TYPES_BY_DOCUMENT: dict[DocumentType, dict[str, type]] = {
    DocumentType.CONTRACT: {
        "agent_name": str,
        "agent_relationship": str,
        "proxy_authority_documents": list,
        "deposit": int,
        "deposit_korean_amount": int,
        "monthly_rent": int,
        "monthly_rent_korean_amount": int,
        "contract_payment": int,
        "contract_payment_korean_amount": int,
        "balance_payment": int,
        "balance_payment_korean_amount": int,
        "contract_payment_date": str,
        "balance_payment_date": str,
        "move_in_date": str,
        "start_date": str,
        "end_date": str,
        "management_fee_present": bool,
        "management_fee": int,
        "management_fee_items": list,
        "deposit_return_clause": str,
        "repair_responsibility_clause": str,
        "main_clauses": list,
        "special_clauses_present": bool,
        "special_clauses": list,
    },
    DocumentType.REGISTRY: {
        "is_joint_ownership": bool,
        "owner_shares": dict,
    },
}

CANONICAL_FIELD_TYPES_BY_DOCUMENT: dict[DocumentType, dict[str, type]] = {
    document_type: {
        **R_FIELD_TYPES_BY_DOCUMENT[document_type],
        **J_FIELD_TYPES_BY_DOCUMENT[document_type],
    }
    for document_type in DocumentType
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
    "R11": frozenset({RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}),
    "R12": frozenset({RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}),
    "R13": frozenset({RuleStatus.CLEAR, RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK, RuleStatus.NOT_APPLICABLE}),
    "R14": frozenset({RuleStatus.CLEAR, RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}),
    "R15": frozenset({RuleStatus.CLEAR, RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}),
    "R16": frozenset({RuleStatus.CHECK_NEEDED}),
    "R17": frozenset({RuleStatus.CLEAR, RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}),
    "R18": frozenset({RuleStatus.CLEAR, RuleStatus.UNCLEAR, RuleStatus.NOT_APPLICABLE, RuleStatus.CANNOT_CHECK}),
    "R19": frozenset({RuleStatus.CLEAR, RuleStatus.NOT_STATED, RuleStatus.CANNOT_CHECK}),
    "R20": frozenset({RuleStatus.CANNOT_CHECK}),
    "R21": frozenset({RuleStatus.CANNOT_CHECK}),
    "R22": frozenset({RuleStatus.CANNOT_CHECK}),
    "R23": frozenset({RuleStatus.CHECK_NEEDED}),
    "R24": frozenset({RuleStatus.CHECK_NEEDED}),
}

ALLOWED_JUDGMENT_STATUSES: dict[str, frozenset[RuleStatus]] = {
    "J01": frozenset(
        {RuleStatus.MATCH, RuleStatus.MISMATCH, RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}
    ),
    "J02": frozenset(
        {RuleStatus.MATCH, RuleStatus.MISMATCH, RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}
    ),
    "J03": frozenset(
        {RuleStatus.CHECK_NEEDED, RuleStatus.NOT_APPLICABLE, RuleStatus.CANNOT_CHECK}
    ),
    "J04": frozenset(
        {RuleStatus.CHECK_NEEDED, RuleStatus.NOT_APPLICABLE, RuleStatus.CANNOT_CHECK}
    ),
    "J05": frozenset(
        {RuleStatus.MATCH, RuleStatus.MISMATCH, RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}
    ),
    "J06": frozenset(
        {RuleStatus.CLEAR, RuleStatus.NOT_STATED, RuleStatus.CHECK_NEEDED, RuleStatus.NOT_APPLICABLE}
    ),
    "J07": frozenset(
        {RuleStatus.MATCH, RuleStatus.MISMATCH, RuleStatus.CHECK_NEEDED, RuleStatus.CANNOT_CHECK}
    ),
    "J08": frozenset(
        {RuleStatus.MATCH, RuleStatus.MISMATCH, RuleStatus.NOT_STATED, RuleStatus.CHECK_NEEDED}
    ),
    "J09": frozenset(
        {
            RuleStatus.CLEAR,
            RuleStatus.UNCLEAR,
            RuleStatus.NOT_STATED,
            RuleStatus.NOT_APPLICABLE,
            RuleStatus.CHECK_NEEDED,
        }
    ),
    "J10": frozenset(
        {RuleStatus.CLEAR, RuleStatus.UNCLEAR, RuleStatus.NOT_STATED, RuleStatus.CHECK_NEEDED}
    ),
    "J11": frozenset(
        {RuleStatus.CLEAR, RuleStatus.UNCLEAR, RuleStatus.NOT_STATED, RuleStatus.CHECK_NEEDED}
    ),
    "J12": frozenset(
        {
            RuleStatus.POSSIBLE_CONFLICT,
            RuleStatus.CLEAR,
            RuleStatus.CHECK_NEEDED,
            RuleStatus.NOT_APPLICABLE,
        }
    ),
    "J13": frozenset(
        {
            RuleStatus.CHECK_NEEDED,
            RuleStatus.NOT_APPLICABLE,
            RuleStatus.CANNOT_CHECK,
        }
    ),
}

RESULT_TYPE_BY_RULE_ID: dict[str, ResultType] = {
    "R01": ResultType.JUDGMENT,
    "R02": ResultType.JUDGMENT,
    "R03": ResultType.FACT_FLAG,
    "R04": ResultType.FACT_FLAG,
    "R05": ResultType.FACT_FLAG,
    "R06": ResultType.JUDGMENT,
    "R07": ResultType.FACT_FLAG,
    "R08": ResultType.JUDGMENT,
    "R09": ResultType.JUDGMENT,
    "R10": ResultType.FACT_FLAG,
    **{f"R{index:02d}": ResultType.JUDGMENT for index in range(11, 25)},
}

CLEAN_STATUSES: frozenset[RuleStatus] = frozenset(
    {RuleStatus.MATCH, RuleStatus.CLEAR, RuleStatus.NOT_APPLICABLE}
)

ACTION_TRIGGER_STATUSES: frozenset[RuleStatus] = frozenset(
    {
        RuleStatus.MISMATCH,
        RuleStatus.UNCLEAR,
        RuleStatus.NOT_STATED,
        RuleStatus.POSSIBLE_CONFLICT,
        RuleStatus.CHECK_NEEDED,
        RuleStatus.CANNOT_CHECK,
    }
)


class SourceEvidence(BaseModel):
    """원문 증거. page/text 키는 항상 존재하고 값은 둘 다 null 허용(ADR 확정)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page: int | None = None
    text: str | None = None


class ClauseSourceField(str, Enum):
    """Classification에 전달할 사용자 확인 완료 조항 원문 필드."""

    DEPOSIT_RETURN = "deposit_return_clause"
    REPAIR_RESPONSIBILITY = "repair_responsibility_clause"
    MAIN_CLAUSES = "main_clauses"
    SPECIAL_CLAUSES = "special_clauses"


class ClauseType(str, Enum):
    """LLM이 제안하는 조항 유형 후보. 최종 판정이 아니다."""

    DEPOSIT_RETURN = "deposit_return"
    REPAIR_RESTORATION = "repair_restoration"
    MANAGEMENT_FEE = "management_fee"
    RIGHTS_CHANGE = "rights_change"
    OTHER = "other"


class ClarityCandidate(str, Enum):
    CLEAR = "명확"
    UNCLEAR = "불명확"
    CHECK_NEEDED = "확인 필요"


class ResponsiblePartyCandidate(str, Enum):
    LANDLORD = "임대인"
    TENANT = "임차인"
    JOINT = "공동"
    UNSPECIFIED = "미지정"


class ClassificationMethod(str, Enum):
    PROVIDER = "provider"
    SAFE_FALLBACK = "safe_fallback"


class ClauseInput(BaseModel):
    """사용자가 확인한 조항 원문 1개. 개인정보 필드는 구조적으로 허용하지 않는다."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    clause_ref: str = Field(min_length=1)
    source_field: ClauseSourceField
    ordinal: int = Field(ge=0, strict=True)
    text: str = Field(min_length=1)
    source_evidence: SourceEvidence = Field(default_factory=SourceEvidence)

    @field_validator("text")
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("조항 원문은 공백일 수 없습니다.")
        return value

    @model_validator(mode="after")
    def _check_clause_ref(self) -> "ClauseInput":
        expected = f"{self.source_field.value}:{self.ordinal}"
        if self.clause_ref != expected:
            raise ValueError(f"clause_ref는 source_field:ordinal 형식이어야 합니다: {expected}")
        return self


class ClassificationInput(BaseModel):
    """확인 완료 InputSnapshot에서 만든 읽기 전용 classification 입력."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    input_snapshot_id: str = Field(min_length=1)
    contract_id: ContractId
    case_id: str | None = None
    clauses: Annotated[list[ClauseInput], AfterValidator(FrozenList)] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def _reject_duplicate_clause_refs(self) -> "ClassificationInput":
        clause_refs = [clause.clause_ref for clause in self.clauses]
        if len(clause_refs) != len(set(clause_refs)):
            raise ValueError("ClassificationInput에 중복 clause_ref가 있습니다.")
        return self


class ClauseCandidate(BaseModel):
    """조항 유형·명확성·책임 주체 후보. 규칙 판정 상태를 포함하지 않는다."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    clause_ref: str = Field(min_length=1)
    clause_type: ClauseType
    clarity_candidate: ClarityCandidate
    responsible_party_candidate: ResponsiblePartyCandidate
    condition_candidates: Annotated[list[str], AfterValidator(FrozenList)] = Field(
        default_factory=list
    )
    review_required: bool

    @field_validator("condition_candidates")
    @classmethod
    def _reject_blank_conditions(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("condition_candidates에는 빈 문자열을 넣을 수 없습니다.")
        return values


class ClassificationResult(BaseModel):
    """입력 snapshot에 종속된 후보와 provider/fallback provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    input_snapshot_id: str = Field(min_length=1)
    contract_id: ContractId
    provider_model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    classification_method: ClassificationMethod
    fallback_reason_code: str | None = None
    candidates: Annotated[list[ClauseCandidate], AfterValidator(FrozenList)] = Field(
        default_factory=list
    )

    @field_validator("provider_model", "prompt_version")
    @classmethod
    def _reject_blank_provenance(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("classification provenance는 공백일 수 없습니다.")
        return value

    @model_validator(mode="after")
    def _check(self) -> "ClassificationResult":
        clause_refs = [candidate.clause_ref for candidate in self.candidates]
        if len(clause_refs) != len(set(clause_refs)):
            raise ValueError("ClassificationResult에 중복 clause_ref 후보가 있습니다.")
        if self.classification_method is ClassificationMethod.PROVIDER:
            if self.fallback_reason_code is not None:
                raise ValueError("provider 결과에는 fallback_reason_code를 기록할 수 없습니다.")
        elif self.fallback_reason_code is None or not self.fallback_reason_code.strip():
            raise ValueError("safe_fallback 결과에는 fallback_reason_code가 필요합니다.")
        return self


def validate_classification_result_for_input(
    classification_input: ClassificationInput,
    result: ClassificationResult,
) -> ClassificationResult:
    """저장·규칙 전달 전 입력 식별자와 clause 참조를 교차 검증한다."""

    if result.schema_version != classification_input.schema_version:
        raise ValueError("ClassificationInput과 ClassificationResult의 schema_version이 다릅니다.")
    if result.input_snapshot_id != classification_input.input_snapshot_id:
        raise ValueError("ClassificationInput과 ClassificationResult의 input_snapshot_id가 다릅니다.")
    if result.contract_id != classification_input.contract_id:
        raise ValueError("ClassificationInput과 ClassificationResult의 contract_id가 다릅니다.")
    input_refs = {clause.clause_ref for clause in classification_input.clauses}
    unknown_refs = [
        candidate.clause_ref
        for candidate in result.candidates
        if candidate.clause_ref not in input_refs
    ]
    if unknown_refs:
        raise ValueError(f"ClassificationResult에 알 수 없는 clause_ref가 있습니다: {unknown_refs}")
    return result


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
    issue_code: FieldIssueCode | None = None
    failure_reason: str | None = None

    @field_validator("extracted_value", "normalized_value", "user_corrected_value")
    @classmethod
    def _no_empty_collection(cls, value: FieldValue) -> FieldValue:
        # 빈 목록 금지: "없음을 읽음"은 값으로, "못 읽음"은 null+failure_reason으로 표현한다.
        # (owner_names 등 list 필드는 non-null이면 항목 1개 이상 — ADR 권장 기준)
        if isinstance(value, list):
            if not value:
                raise ValueError("빈 목록은 허용하지 않습니다. 판독 실패는 null과 failure_reason으로 표현하세요.")
            if not all(isinstance(item, str) and item for item in value):
                raise ValueError("목록 값은 비어 있지 않은 문자열이어야 합니다.")
        if isinstance(value, dict):
            if not value:
                raise ValueError("빈 매핑은 허용하지 않습니다. 값이 없으면 null을 사용하세요.")
            if not all(
                isinstance(key, str)
                and bool(key.strip())
                and isinstance(item, str)
                and bool(item.strip())
                for key, item in value.items()
            ):
                raise ValueError("매핑 키와 값은 비어 있지 않은 문자열이어야 합니다.")
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
    for key, mapped_field in fields.items():
        if key != mapped_field.field_name:
            raise ValueError(
                f"fields 키 '{key}'와 field_name '{mapped_field.field_name}'이 다릅니다."
            )
    missing = REQUIRED_FIELDS_BY_TYPE[document_type] - fields.keys()
    if missing:
        raise ValueError(
            f"{document_type.value} 추출 결과에 필수 키가 없습니다: {sorted(missing)} "
            "(값을 못 읽어도 키는 null로 존재해야 합니다)"
        )
    for field_name, expected_type in CANONICAL_FIELD_TYPES_BY_DOCUMENT[document_type].items():
        typed_field = fields.get(field_name)
        if typed_field is None:
            continue
        for value_name in ("extracted_value", "normalized_value", "user_corrected_value"):
            value = getattr(typed_field, value_name)
            if value is None:
                continue
            valid = (
                isinstance(value, expected_type)
                if expected_type in {list, dict}
                else type(value) is expected_type
            )
            if not valid:
                expected_name = (
                    "list[str]"
                    if expected_type is list
                    else "dict[str, str]"
                    if expected_type is dict
                    else expected_type.__name__
                )
                raise ValueError(
                    f"{document_type.value}.{field_name}.{value_name}는 "
                    f"{expected_name} 또는 null이어야 합니다."
                )
    return fields


class DocumentExtraction(BaseModel):
    """문서 1건의 추출 결과. 핵심 R01~R10 필수 키는 값이 null이어도 항상 존재한다."""

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
    contract_context: ContractContext
    confirmed_fields: SnapshotFields
    confirmed_at: datetime

    @model_validator(mode="after")
    def _check(self) -> "InputSnapshot":
        if self.contract_context.contract_id != self.contract_id:
            raise ValueError("InputSnapshot과 ContractContext의 contract_id가 다릅니다.")
        for doc_fields in (self.confirmed_fields.contract, self.confirmed_fields.registry):
            for item in doc_fields.values():
                if item.verification_status is VerificationStatus.UNVERIFIED:
                    raise ValueError(
                        f"스냅샷에는 확인 완료(confirmed/corrected) 필드만 담을 수 있습니다: {item.field_name}"
                    )
        return self


def _validate_judgment_ids(judgment_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not judgment_ids:
        raise ValueError("judgment_ids는 1개 이상이어야 합니다.")
    if len(judgment_ids) != len(set(judgment_ids)):
        raise ValueError("judgment_ids에 중복이 있습니다.")
    unknown = [judgment_id for judgment_id in judgment_ids if judgment_id not in JUDGMENT_INPUT_SPECS]
    if unknown:
        raise ValueError(f"알 수 없는 judgment_id입니다: {unknown}")
    expected_order = tuple(
        judgment_id for judgment_id in JUDGMENT_IDS if judgment_id in judgment_ids
    )
    if judgment_ids != expected_order:
        raise ValueError("judgment_ids는 canonical 순서를 따라야 합니다.")
    return judgment_ids


def _required_judgment_fields(
    judgment_ids: tuple[str, ...], document_type: DocumentType
) -> tuple[str, ...]:
    attribute = (
        "contract_fields"
        if document_type is DocumentType.CONTRACT
        else "registry_fields"
    )
    ordered: list[str] = []
    for judgment_id in judgment_ids:
        for field_name in getattr(JUDGMENT_INPUT_SPECS[judgment_id], attribute):
            if field_name not in ordered:
                ordered.append(field_name)
    return tuple(ordered)


def _validate_judgment_field_map(
    values: dict[str, ExtractedField],
    *,
    judgment_ids: tuple[str, ...],
    document_type: DocumentType,
) -> None:
    required = _required_judgment_fields(judgment_ids, document_type)
    if set(values) != set(required):
        missing = sorted(set(required) - values.keys())
        unexpected = sorted(values.keys() - set(required))
        raise ValueError(
            f"{document_type.value} J 입력 필드 불일치: "
            f"missing={missing}, unexpected={unexpected}"
        )
    types = CANONICAL_FIELD_TYPES_BY_DOCUMENT[document_type]
    for field_name, field in values.items():
        if field.field_name != field_name:
            raise ValueError(
                f"{document_type.value} J 입력 키 '{field_name}'와 "
                f"field_name '{field.field_name}'이 다릅니다."
            )
        if field.verification_status is VerificationStatus.UNVERIFIED:
            raise ValueError(
                f"{document_type.value}.{field_name} J 입력은 확인 완료 상태여야 합니다."
            )
        value = field.effective_value
        if value is None:
            if field.issue_code is None:
                raise ValueError(
                    f"{document_type.value}.{field_name}의 값이 null이면 "
                    "J 입력에는 issue_code가 필요합니다."
                )
            continue
        expected_type = types[field_name]
        valid = (
            isinstance(value, expected_type)
            if expected_type in {list, dict}
            else type(value) is expected_type
        )
        if not valid:
            raise ValueError(
                f"{document_type.value}.{field_name} J 입력 타입이 올바르지 않습니다."
            )


FrozenExtractedFieldMap = Annotated[
    dict[str, ExtractedField], AfterValidator(FrozenDict)
]
FrozenClauseCandidateList = Annotated[
    list[ClauseCandidate], AfterValidator(FrozenList)
]

_CLASSIFICATION_SOURCE_FIELDS = frozenset(
    source_field.value for source_field in ClauseSourceField
)


def legacy_classification_candidates(
    contract_fields: Mapping[str, ExtractedField],
) -> list[ClauseCandidate]:
    """전환 기간 구 명확성 후보를 J 입력 후보로만 변환한다."""

    candidates: list[ClauseCandidate] = []
    mappings = (
        (
            "deposit_return_condition",
            "deposit_return_clause",
            ClauseType.DEPOSIT_RETURN,
        ),
        (
            "repair_responsibility",
            "repair_responsibility_clause",
            ClauseType.REPAIR_RESTORATION,
        ),
    )
    for legacy_name, raw_name, clause_type in mappings:
        legacy_field = contract_fields.get(legacy_name)
        raw_field = contract_fields.get(raw_name)
        if legacy_field is None or raw_field is None:
            continue
        legacy_value = legacy_field.effective_value
        raw_value = raw_field.effective_value
        if not isinstance(raw_value, str):
            continue
        try:
            clarity = ClarityCandidate(legacy_value)
        except (TypeError, ValueError):
            continue
        parties = {party for party in ("임대인", "임차인") if party in raw_value}
        responsible_party = (
            ResponsiblePartyCandidate.JOINT
            if len(parties) == 2
            else ResponsiblePartyCandidate.LANDLORD
            if parties == {"임대인"}
            else ResponsiblePartyCandidate.TENANT
            if parties == {"임차인"}
            else ResponsiblePartyCandidate.UNSPECIFIED
        )
        candidates.append(
            ClauseCandidate(
                clause_ref=f"{raw_name}:0",
                clause_type=clause_type,
                clarity_candidate=clarity,
                responsible_party_candidate=responsible_party,
                condition_candidates=(
                    [raw_value]
                    if clause_type is ClauseType.DEPOSIT_RETURN
                    and clarity is ClarityCandidate.CLEAR
                    else []
                ),
                review_required=clarity is ClarityCandidate.CHECK_NEEDED,
            )
        )
    return candidates


class JudgmentInput(BaseModel):
    """사용자 확인 완료 snapshot에서 만든 J 판정 전용 불변 effective input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    input_snapshot_id: str = Field(min_length=1)
    contract_id: ContractId
    case_id: str | None = None
    judgment_ids: tuple[str, ...] = Field(min_length=1, max_length=len(JUDGMENT_IDS))
    contract_context: ContractContext
    contract_fields: FrozenExtractedFieldMap
    registry_fields: FrozenExtractedFieldMap
    classification_candidates: FrozenClauseCandidateList = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _adapt_v18_legacy_fields(cls, data: object) -> object:
        """구 골드셋의 후보 필드를 canonical 후보로 바꿔 읽기만 호환한다."""

        if not isinstance(data, dict):
            return data
        context = data.get("contract_context")
        context_version: object
        if isinstance(context, ContractContext):
            context_version = context.schema_version
        elif isinstance(context, dict):
            context_version = context.get("schema_version")
        else:
            return data
        if context_version != "1.8.0":
            return data

        judgment_ids = tuple(data.get("judgment_ids", ()))
        contract_fields = data.get("contract_fields")
        if not judgment_ids or not isinstance(contract_fields, Mapping):
            return data

        parsed_fields = {
            name: field
            if isinstance(field, ExtractedField)
            else ExtractedField.model_validate(field)
            for name, field in contract_fields.items()
        }
        required = set(_required_judgment_fields(judgment_ids, DocumentType.CONTRACT))
        normalized = dict(data)
        normalized.setdefault("schema_version", context_version)
        normalized["contract_fields"] = {
            name: field for name, field in parsed_fields.items() if name in required
        }
        if not normalized.get("classification_candidates"):
            normalized["classification_candidates"] = legacy_classification_candidates(
                parsed_fields
            )
        return normalized

    @model_validator(mode="after")
    def _check(self) -> "JudgmentInput":
        _validate_judgment_ids(self.judgment_ids)
        if self.contract_context.contract_id != self.contract_id:
            raise ValueError("JudgmentInput과 ContractContext의 contract_id가 다릅니다.")
        _validate_judgment_field_map(
            self.contract_fields,
            judgment_ids=self.judgment_ids,
            document_type=DocumentType.CONTRACT,
        )
        _validate_judgment_field_map(
            self.registry_fields,
            judgment_ids=self.judgment_ids,
            document_type=DocumentType.REGISTRY,
        )
        candidate_refs = [
            candidate.clause_ref for candidate in self.classification_candidates
        ]
        if len(candidate_refs) != len(set(candidate_refs)):
            raise ValueError("JudgmentInput에 중복 classification clause_ref가 있습니다.")
        allowed_sources = set(self.contract_fields) & _CLASSIFICATION_SOURCE_FIELDS
        invalid_refs = [
            candidate.clause_ref
            for candidate in self.classification_candidates
            if candidate.clause_ref.partition(":")[0] not in allowed_sources
        ]
        if invalid_refs:
            raise ValueError(
                "JudgmentInput 판정 범위 밖 classification clause_ref가 있습니다: "
                f"{invalid_refs}"
            )
        return self


def build_judgment_input(
    snapshot: InputSnapshot,
    *,
    judgment_ids: tuple[str, ...] = JUDGMENT_IDS,
    classification_result: ClassificationResult | None = None,
) -> JudgmentInput:
    """확인 완료 원문과 검증된 classification 후보를 J 입력으로 복사한다."""

    judgment_ids = _validate_judgment_ids(judgment_ids)
    contract_names = _required_judgment_fields(judgment_ids, DocumentType.CONTRACT)
    registry_names = _required_judgment_fields(judgment_ids, DocumentType.REGISTRY)
    missing_contract = [
        field_name
        for field_name in contract_names
        if field_name not in snapshot.confirmed_fields.contract
    ]
    missing_registry = [
        field_name
        for field_name in registry_names
        if field_name not in snapshot.confirmed_fields.registry
    ]
    if missing_contract or missing_registry:
        raise ValueError(
            "J 입력 필드가 snapshot에 없습니다: "
            f"contract={missing_contract}, registry={missing_registry}"
        )
    if classification_result is not None:
        if classification_result.schema_version != snapshot.schema_version:
            raise ValueError(
                "InputSnapshot과 ClassificationResult의 schema_version이 다릅니다."
            )
        if classification_result.input_snapshot_id != snapshot.input_snapshot_id:
            raise ValueError(
                "InputSnapshot과 ClassificationResult의 input_snapshot_id가 다릅니다."
            )
        if classification_result.contract_id != snapshot.contract_id:
            raise ValueError(
                "InputSnapshot과 ClassificationResult의 contract_id가 다릅니다."
            )
    classification_sources = set(contract_names) & _CLASSIFICATION_SOURCE_FIELDS
    source_candidates = (
        classification_result.candidates
        if classification_result is not None
        else legacy_classification_candidates(snapshot.confirmed_fields.contract)
    )
    classification_candidates = [
        candidate
        for candidate in source_candidates
        if candidate.clause_ref.partition(":")[0] in classification_sources
    ]
    return JudgmentInput(
        schema_version=snapshot.schema_version,
        input_snapshot_id=snapshot.input_snapshot_id,
        contract_id=snapshot.contract_id,
        case_id=snapshot.case_id,
        judgment_ids=judgment_ids,
        contract_context=snapshot.contract_context,
        contract_fields={
            field_name: snapshot.confirmed_fields.contract[field_name]
            for field_name in contract_names
        },
        registry_fields={
            field_name: snapshot.confirmed_fields.registry[field_name]
            for field_name in registry_names
        },
        classification_candidates=classification_candidates,
    )


class OfficialSource(BaseModel):
    """공식 근거 참조(정적 카탈로그 항목). 원문 증거(SourceEvidence)와 구분."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    article_or_section: str | None = None
    title: str
    institution: str
    # 현행 source_inventory.csv에 요약이 비어 있는 항목이 있어 null 허용.
    summary: str | None = None
    # 화면 "전체 보기"용 공식자료 전체 원문. 검색 청크(summary)와 별개 — 로컬 원문이 있는
    # 근거만 채워지고 없으면 null(화면은 summary로 폴백). RuleStatus·urgency와 무관.
    source_text: str | None = None
    source_url: str | None = None
    # 이 근거를 회수한 검색 방식(관찰용). RAG enrich에서 실제 사용된 방식을 기록한다.
    # 정적 카탈로그 항목·평가용 정답에는 None. RuleStatus·urgency를 바꾸지 않는다.
    retrieval_method: Literal["bm25", "vector", "hybrid", "rerank"] | None = None


class ReferenceCase(BaseModel):
    """판정 근거와 분리해 보여주는 검증된 유사 참고 사례."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    published_at: date | None = None
    source_url: str
    summary: str = Field(min_length=1)
    verification_scope: str = Field(min_length=1)


class DamagePatternStatus(str, Enum):
    """화면용 피해 유형 관련성. 규칙 상태·시급도를 대체하지 않는다."""

    RELATED_SIGNAL = "관련 확인 신호 있음"
    NO_SIGNAL_IN_SUBMITTED_DOCS = "제출 자료에서 관련 신호 미확인"
    CANNOT_ASSESS = "자료 부족으로 확인 불가"
    PREVENTIVE_CHECK = "예방 확인 필요"


class DamagePatternComparison(BaseModel):
    """기존 R/J 판정을 피해 유형 관점으로 결정적으로 묶은 표시용 결과."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pattern_id: str = Field(pattern=r"^DP\d{2}$")
    pattern_name: str = Field(min_length=1)
    status: DamagePatternStatus
    reason: str = Field(min_length=1)
    related_rule_ids: tuple[str, ...] = ()
    related_judgment_ids: tuple[str, ...] = ()
    limitations: str = Field(min_length=1)
    official_sources: tuple[OfficialSource, ...] = ()
    reference_cases: tuple[ReferenceCase, ...] = ()


_RuleId = Annotated[str, Field(pattern=r"^R\d{2}$")]
_JudgmentId = Annotated[str, Field(pattern=_JUDGMENT_ID_PATTERN)]


class SpecialClauseReview(BaseModel):
    """사용자 확인 특약 1개를 기존 R/J 결과에 연결한 카드.

    상태·시급도는 규칙 엔진이 정한 연결 R/J 결과를 그대로 반영하며 새 판정을 만들지 않는다.
    RAG 근거는 evidence_sources로만 붙고, 없으면 빈 튜플을 유지한다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    clause_id: str = Field(min_length=1)
    original_text: str = Field(min_length=1)
    catalog_ids: tuple[str, ...] = ()
    match_method: Literal["catalog_exact", "catalog_pattern", "unmatched"]
    related_rule_ids: tuple[_RuleId, ...] = ()
    related_judgment_ids: tuple[_JudgmentId, ...] = ()
    status: RuleStatus
    urgency: Urgency
    reason: str = Field(min_length=1)
    triggers_actions: bool
    evidence_sources: tuple[OfficialSource, ...] = ()
    limitations: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> "SpecialClauseReview":
        if not self.related_rule_ids and not self.related_judgment_ids:
            raise ValueError(
                "특약 카드는 related_rule_ids나 related_judgment_ids 중 하나 이상을 연결해야 합니다."
            )
        expected_trigger = self.status in ACTION_TRIGGER_STATUSES
        if self.triggers_actions is not expected_trigger:
            raise ValueError(
                f"status={self.status.value}의 triggers_actions는 "
                f"{str(expected_trigger).lower()}이어야 합니다."
            )
        if self.match_method == "unmatched":
            if self.catalog_ids:
                raise ValueError("match_method가 unmatched이면 catalog_ids는 비어 있어야 합니다.")
        elif not self.catalog_ids:
            raise ValueError("catalog 매칭이면 catalog_ids가 하나 이상 있어야 합니다.")
        return self


class RuleResult(BaseModel):
    """규칙 결과 1개. 결과 역할·행동 활성화·상태·시급도를 분리한다."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(pattern=r"^R\d{2}$")
    rule_name: str
    judgment_id: str | None = None
    result_type: ResultType
    triggers_actions: bool
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
        expected_type = RESULT_TYPE_BY_RULE_ID.get(self.rule_id)
        if expected_type is not None and self.result_type is not expected_type:
            raise ValueError(
                f"{self.rule_id}의 result_type은 {expected_type.value}이어야 합니다: "
                f"{self.result_type.value}"
            )
        expected_trigger = self.status in ACTION_TRIGGER_STATUSES
        if self.triggers_actions is not expected_trigger:
            raise ValueError(
                f"status={self.status.value}의 triggers_actions는 "
                f"{str(expected_trigger).lower()}이어야 합니다."
            )
        return self


class JudgmentResult(BaseModel):
    """J01~J12 판정 1개. R 규칙 결과와 별도 축으로 저장한다."""

    model_config = ConfigDict(extra="forbid")

    judgment_id: str = Field(pattern=_JUDGMENT_ID_PATTERN)
    judgment_name: str = Field(min_length=1)
    status: RuleStatus
    urgency: Urgency
    triggers_actions: bool
    reason: str = Field(min_length=1)
    question: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    evidence_sources: list[OfficialSource] = Field(default_factory=list)
    limitations: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> "JudgmentResult":
        allowed = ALLOWED_JUDGMENT_STATUSES[self.judgment_id]
        if self.status not in allowed:
            values = ", ".join(sorted(status.value for status in allowed))
            raise ValueError(
                f"{self.judgment_id}에서 허용되지 않는 status입니다: "
                f"{self.status.value} (허용: {values})"
            )
        expected_trigger = self.status in ACTION_TRIGGER_STATUSES
        if self.triggers_actions is not expected_trigger:
            raise ValueError(
                f"status={self.status.value}의 triggers_actions는 "
                f"{str(expected_trigger).lower()}이어야 합니다."
            )
        if self.status is RuleStatus.CANNOT_CHECK:
            if self.urgency is not Urgency.NOT_ANALYZABLE:
                raise ValueError("확인 불가 판정의 urgency는 분석 불가여야 합니다.")
        elif self.urgency is Urgency.NOT_ANALYZABLE:
            raise ValueError("분석 불가 urgency는 확인 불가 판정에만 사용할 수 있습니다.")
        return self


class AnalysisRunResult(BaseModel):
    """분석 실행 1회의 R 규칙 결과와 J 판정 결과 묶음."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = SCHEMA_VERSION
    analysis_run_id: str = Field(min_length=1)
    input_snapshot_id: str = Field(min_length=1)
    contract_id: ContractId
    case_id: str | None = None
    # v1.9의 기존 R01~R10 저장 결과도 계속 읽되, 신규 실행은 R01~R24를 생성한다.
    results: list[RuleResult] = Field(min_length=10, max_length=24)
    # 1단계 R-only 실행은 빈 목록, 2단계 J 확장 실행은 J01~J12 전체를 요구한다.
    judgments: list[JudgmentResult] = Field(default_factory=list, max_length=len(JUDGMENT_IDS))
    # 과거 결과에는 필드가 없으므로 빈 목록을 기본값으로 유지한다.
    damage_patterns: list[DamagePatternComparison] = Field(default_factory=list, max_length=8)
    # 특약별 근거 카드. 과거 결과에는 없으므로 빈 목록이 기본값(하위 호환).
    special_clause_reviews: list[SpecialClauseReview] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> "AnalysisRunResult":
        rule_ids = [result.rule_id for result in self.results]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("results에 중복 rule_id가 있습니다.")
        allowed_sequences = (
            [f"R{index:02d}" for index in range(1, 11)],
            [f"R{index:02d}" for index in range(1, 25)],
        )
        if rule_ids not in allowed_sequences:
            raise ValueError("results에는 R01~R10 또는 R01~R24가 순서대로 각각 정확히 1개씩 있어야 합니다.")
        if self.judgments:
            judgment_ids = [result.judgment_id for result in self.judgments]
            # 레거시 J01~J12는 영구히 허용한다. 저장된 과거 결과를 계속 읽기 위해서다.
            allowed_judgment_sequences = (
                [f"J{index:02d}" for index in range(1, 13)],
                list(JUDGMENT_IDS),
            )
            if judgment_ids not in allowed_judgment_sequences:
                raise ValueError(
                    "judgments에는 레거시 J01~J12 또는 현행 canonical 순서가 "
                    "각각 정확히 1개씩 있거나, R-only 실행을 나타내는 빈 목록이어야 합니다."
                )
        if self.damage_patterns:
            pattern_ids = [item.pattern_id for item in self.damage_patterns]
            expected_patterns = [f"DP{index:02d}" for index in range(1, 9)]
            if pattern_ids != expected_patterns:
                raise ValueError("damage_patterns에는 DP01~DP08이 순서대로 각각 정확히 1개씩 있어야 합니다.")
        if self.special_clause_reviews:
            clause_ids = [review.clause_id for review in self.special_clause_reviews]
            if len(clause_ids) != len(set(clause_ids)):
                raise ValueError("special_clause_reviews에 중복 clause_id가 있습니다.")
            rule_states = {result.rule_id: (result.status, result.urgency) for result in self.results}
            judgment_states = {
                judgment.judgment_id: (judgment.status, judgment.urgency)
                for judgment in self.judgments
            }
            for review in self.special_clause_reviews:
                linked: list[tuple[RuleStatus, Urgency]] = []
                for rule_id in review.related_rule_ids:
                    if rule_id not in rule_states:
                        raise ValueError(
                            f"특약 카드가 분석 결과에 없는 rule_id를 연결했습니다: {rule_id}"
                        )
                    linked.append(rule_states[rule_id])
                for judgment_id in review.related_judgment_ids:
                    if judgment_id not in judgment_states:
                        raise ValueError(
                            f"특약 카드가 분석 결과에 없는 judgment_id를 연결했습니다: {judgment_id}"
                        )
                    linked.append(judgment_states[judgment_id])
                if (review.status, review.urgency) not in linked:
                    raise ValueError(
                        "특약 카드의 status·urgency가 연결된 Python 규칙/판정 결과와 일치하지 않습니다."
                    )
        return self


class GenerationMethod(str, Enum):
    """사용자 안내 생성 방식 — provider와 안전한 template fallback을 구분한다."""

    PROVIDER = "provider"
    TEMPLATE_FALLBACK = "template_fallback"

class GuidanceActionItem(BaseModel):
    """R/J 생성 체크리스트·계약 직후 행동의 안정 저장 식별자."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_key: str = Field(
        pattern=r"^(?:R\d{2}|J(?:0[1-9]|1[0-2])):(checklist|post_action):[0-9a-f]{12}$",
        max_length=100,
    )
    text: str = Field(min_length=1)


def _validate_unique_non_empty(values: tuple[str, ...], *, label: str) -> tuple[str, ...]:
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} 목록에는 빈 문자열을 넣을 수 없습니다.")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} 목록에는 중복 값을 넣을 수 없습니다.")
    return values


class RuleGuidance(BaseModel):
    """검증 또는 fallback을 마친 규칙 1개의 공개 사용자 안내."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(pattern=r"^R\d{2}$")
    explanation: str = Field(min_length=1)
    questions: tuple[str, ...] = ()
    request_templates: tuple[str, ...] = ()
    signing_checklist: tuple[str, ...] = ()
    post_contract_actions: tuple[str, ...] = ()
    signing_checklist_items: tuple[GuidanceActionItem, ...] = ()
    post_contract_action_items: tuple[GuidanceActionItem, ...] = ()
    source_ids: tuple[str, ...] = ()
    generation_method: GenerationMethod
    provider_model: str | None = None
    fallback_reason: str | None = None

    @field_validator(
        "questions", "request_templates", "signing_checklist", "post_contract_actions", "source_ids"
    )
    @classmethod
    def _unique_non_empty(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_unique_non_empty(values, label="안내")

    @model_validator(mode="after")
    def _method_metadata(self) -> "RuleGuidance":
        if self.generation_method is GenerationMethod.PROVIDER:
            if self.provider_model is None or self.fallback_reason is not None:
                raise ValueError("provider 생성에는 provider_model만 필요합니다.")
        elif self.fallback_reason is None or self.provider_model is not None:
            raise ValueError("template fallback에는 fallback_reason만 필요합니다.")
        return self
    @model_validator(mode="after")
    def _action_items_match_legacy_text(self) -> "RuleGuidance":
        pairs = (
            (self.signing_checklist, self.signing_checklist_items, "checklist"),
            (self.post_contract_actions, self.post_contract_action_items, "post_action"),
        )
        for legacy, items, kind in pairs:
            if items and tuple(item.text for item in items) != legacy:
                raise ValueError(f"{kind} 안정 항목은 기존 문자열 목록과 일치해야 합니다.")
            if len({item.item_key for item in items}) != len(items):
                raise ValueError(f"{kind} item_key는 중복될 수 없습니다.")
        return self


class JudgmentGuidance(BaseModel):
    """검증 또는 fallback을 마친 J01~J12 판정 1개의 공개 사용자 안내."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    judgment_id: str = Field(pattern=r"^J(?:0[1-9]|1[0-2])$")
    explanation: str = Field(min_length=1)
    questions: tuple[str, ...] = ()
    request_templates: tuple[str, ...] = ()
    signing_checklist: tuple[str, ...] = ()
    post_contract_actions: tuple[str, ...] = ()
    signing_checklist_items: tuple[GuidanceActionItem, ...] = ()
    post_contract_action_items: tuple[GuidanceActionItem, ...] = ()
    source_ids: tuple[str, ...] = ()
    generation_method: GenerationMethod
    provider_model: str | None = None
    fallback_reason: str | None = None

    @field_validator(
        "questions", "request_templates", "signing_checklist", "post_contract_actions", "source_ids"
    )
    @classmethod
    def _unique_non_empty(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_unique_non_empty(values, label="J 안내")

    @model_validator(mode="after")
    def _method_metadata(self) -> "JudgmentGuidance":
        if self.generation_method is GenerationMethod.PROVIDER:
            if self.provider_model is None or self.fallback_reason is not None:
                raise ValueError("provider 생성에는 provider_model만 필요합니다.")
        elif self.fallback_reason is None or self.provider_model is not None:
            raise ValueError("template fallback에는 fallback_reason만 필요합니다.")
        return self

    @model_validator(mode="after")
    def _action_items_match_legacy_text(self) -> "JudgmentGuidance":
        pairs = (
            (self.signing_checklist, self.signing_checklist_items, "checklist"),
            (self.post_contract_actions, self.post_contract_action_items, "post_action"),
        )
        for legacy, items, kind in pairs:
            if items and tuple(item.text for item in items) != legacy:
                raise ValueError(f"{kind} 안정 항목은 기존 문자열 목록과 일치해야 합니다.")
            if len({item.item_key for item in items}) != len(items):
                raise ValueError(f"{kind} item_key는 중복될 수 없습니다.")
        return self


class SpecialClauseGuidance(BaseModel):
    """근거가 연결된 특약 1개의 공개 사용자 안내.

    쉬운 설명·확인 질문·수정 요청 문구와, 그 근거로 쓴 source_id만 담는다.
    새 판정 상태나 위험 점수를 만들지 않고, source_ids는 특약 카드 근거의 부분집합이어야 한다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    clause_id: str = Field(min_length=1)
    plain_explanation: str = Field(min_length=1)
    confirmation_questions: tuple[str, ...] = ()
    revision_requests: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    generation_method: GenerationMethod

    @field_validator("confirmation_questions", "revision_requests", "source_ids")
    @classmethod
    def _unique_non_empty(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_unique_non_empty(values, label="특약 안내")


class StageGuidance(BaseModel):
    """ContractContext와 J 판정을 결합한 단계별 사용자 행동 묶음."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_context: ContractContext
    before_deposit_questions: tuple[str, ...] = ()
    signing_checklist: tuple[str, ...] = ()
    post_contract_actions: tuple[str, ...] = ()
    record_retention: tuple[str, ...] = ()
    before_contract_actions: tuple[str, ...] = ()
    during_contract_actions: tuple[str, ...] = ()
    closing_day_actions: tuple[str, ...] = ()
    after_contract_actions: tuple[str, ...] = ()

    @field_validator(
        "before_deposit_questions",
        "signing_checklist",
        "post_contract_actions",
        "record_retention",
        "before_contract_actions",
        "during_contract_actions",
        "closing_day_actions",
        "after_contract_actions",
    )
    @classmethod
    def _unique_non_empty(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_unique_non_empty(values, label="단계별 안내")


class GenerationResult(BaseModel):
    """AnalysisRunResult와 분리 저장하는 guardrail 통과 생성 결과."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion = SCHEMA_VERSION
    analysis_run_id: str = Field(min_length=1)
    prompt_version: GenerationPromptVersion
    items: tuple[RuleGuidance, ...]
    judgment_items: tuple[JudgmentGuidance, ...]
    stage_guidance: StageGuidance
    # 특약별 안내. 과거 생성 결과에는 없으므로 빈 튜플이 기본값(하위 호환).
    special_clause_items: tuple[SpecialClauseGuidance, ...] = ()
    guardrail_passed: Literal[True] = True

    @model_validator(mode="after")
    def _unique_rules(self) -> "GenerationResult":
        rule_ids = [item.rule_id for item in self.items]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("생성 결과에는 중복 rule_id를 넣을 수 없습니다.")
        judgment_ids = [item.judgment_id for item in self.judgment_items]
        if len(judgment_ids) != len(set(judgment_ids)):
            raise ValueError("생성 결과에는 중복 judgment_id를 넣을 수 없습니다.")
        clause_ids = [item.clause_id for item in self.special_clause_items]
        if len(clause_ids) != len(set(clause_ids)):
            raise ValueError("생성 결과에는 중복 특약 clause_id를 넣을 수 없습니다.")
        return self


def validate_generation_result_for_analysis(
    analysis: AnalysisRunResult, generation: GenerationResult
) -> GenerationResult:
    """저장 전 분석 결과와 생성 결과의 식별자·공식 근거 연결을 검증한다."""

    if generation.analysis_run_id != analysis.analysis_run_id:
        raise ValueError("GenerationResult와 AnalysisRunResult의 analysis_run_id가 다릅니다.")
    if generation.stage_guidance.contract_context.contract_id != analysis.contract_id:
        raise ValueError("GenerationResult ContractContext의 contract_id가 분석 결과와 다릅니다.")
    rules = {result.rule_id: result for result in analysis.results}
    for rule_guidance in generation.items:
        rule = rules.get(rule_guidance.rule_id)
        if rule is None:
            raise ValueError(
                f"분석 결과에 없는 rule_id입니다: {rule_guidance.rule_id}"
            )
        allowed_source_ids = {source.source_id for source in rule.evidence_sources}
        unknown_source_ids = set(rule_guidance.source_ids) - allowed_source_ids
        if unknown_source_ids:
            raise ValueError(
                f"{rule_guidance.rule_id}의 공식 근거가 아닌 source_id입니다: "
                f"{sorted(unknown_source_ids)}"
            )
    judgments = {result.judgment_id: result for result in analysis.judgments}
    for judgment_guidance in generation.judgment_items:
        judgment = judgments.get(judgment_guidance.judgment_id)
        if judgment is None:
            raise ValueError(
                "분석 결과에 없는 judgment_id입니다: "
                f"{judgment_guidance.judgment_id}"
            )
        allowed_source_ids = {
            source.source_id for source in judgment.evidence_sources
        }
        unknown_source_ids = set(judgment_guidance.source_ids) - allowed_source_ids
        if unknown_source_ids:
            raise ValueError(
                f"{judgment_guidance.judgment_id}의 공식 근거가 아닌 source_id입니다: "
                f"{sorted(unknown_source_ids)}"
            )
    reviews = {review.clause_id: review for review in analysis.special_clause_reviews}
    for clause_guidance in generation.special_clause_items:
        review = reviews.get(clause_guidance.clause_id)
        if review is None:
            raise ValueError(
                f"분석 결과에 없는 특약 clause_id입니다: {clause_guidance.clause_id}"
            )
        allowed_source_ids = {source.source_id for source in review.evidence_sources}
        unknown_source_ids = set(clause_guidance.source_ids) - allowed_source_ids
        if unknown_source_ids:
            raise ValueError(
                f"{clause_guidance.clause_id}의 공식 근거가 아닌 source_id입니다: "
                f"{sorted(unknown_source_ids)}"
            )
    return generation


class FieldCorrection(BaseModel):
    """사용자 수정 요청 1건 — corrected_value는 null 불가(수정 취소는 별도 흐름)."""

    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    field_name: str = Field(min_length=1)
    corrected_value: str | int | bool | list[str] | dict[str, str]

    @field_validator("corrected_value")
    @classmethod
    def _no_empty_collection(
        cls, value: str | int | bool | list[str] | dict[str, str]
    ) -> str | int | bool | list[str] | dict[str, str]:
        if isinstance(value, (list, dict)) and not value:
            raise ValueError("빈 목록·매핑으로 수정할 수 없습니다.")
        return value

    @model_validator(mode="after")
    def _check_canonical_field_type(self) -> "FieldCorrection":
        expected_type = CANONICAL_FIELD_TYPES_BY_DOCUMENT[self.document_type].get(
            self.field_name
        )
        if expected_type is None:
            return self
        valid = (
            isinstance(self.corrected_value, expected_type)
            if expected_type in {list, dict}
            else type(self.corrected_value) is expected_type
        )
        if not valid:
            expected_name = (
                "list[str]"
                if expected_type is list
                else "dict[str, str]"
                if expected_type is dict
                else expected_type.__name__
            )
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
