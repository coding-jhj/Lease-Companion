"""InputSnapshot에서 J10~J12 대상 조항만 복사하는 순수 builder."""

from collections.abc import Iterable

from lease_companion_ai.schemas.unified import (
    ClassificationInput,
    ClauseInput,
    ClauseSourceField,
    ExtractedField,
    InputSnapshot,
)

_SINGLE_CLAUSE_FIELDS: tuple[ClauseSourceField, ...] = (
    ClauseSourceField.DEPOSIT_RETURN,
    ClauseSourceField.REPAIR_RESPONSIBILITY,
)
_LIST_CLAUSE_FIELDS: tuple[ClauseSourceField, ...] = (
    ClauseSourceField.MAIN_CLAUSES,
    ClauseSourceField.SPECIAL_CLAUSES,
)


def _non_blank_strings(values: Iterable[str]) -> list[str]:
    """공백 항목은 제외하되 사용자 확인 원문 문자열 자체는 변경하지 않는다."""

    return [value for value in values if value.strip()]


def _single_clause(field: ExtractedField | None) -> list[str]:
    if field is None or field.effective_value is None:
        return []
    value = field.effective_value
    if not isinstance(value, str):
        raise TypeError(f"{field.field_name} effective_value는 문자열이어야 합니다.")
    return _non_blank_strings([value])


def _clause_list(field: ExtractedField | None) -> list[str]:
    if field is None or field.effective_value is None:
        return []
    value = field.effective_value
    if not isinstance(value, list):
        raise TypeError(f"{field.field_name} effective_value는 문자열 목록이어야 합니다.")
    if not all(isinstance(item, str) for item in value):
        raise TypeError(f"{field.field_name} effective_value 항목은 문자열이어야 합니다.")
    return _non_blank_strings(value)


def _clause_inputs(
    source_field: ClauseSourceField,
    field: ExtractedField | None,
    texts: list[str],
) -> list[ClauseInput]:
    if field is None:
        return []
    return [
        ClauseInput(
            clause_ref=f"{source_field.value}:{ordinal}",
            source_field=source_field,
            ordinal=ordinal,
            text=text,
            source_evidence=field.source_evidence,
        )
        for ordinal, text in enumerate(texts)
    ]


def build_classification_input(snapshot: InputSnapshot) -> ClassificationInput:
    """확인 완료 snapshot에서 개인정보를 제외한 조항 원문만 복사한다."""

    contract_fields = snapshot.confirmed_fields.contract
    clauses: list[ClauseInput] = []

    for source_field in _SINGLE_CLAUSE_FIELDS:
        field = contract_fields.get(source_field.value)
        clauses.extend(_clause_inputs(source_field, field, _single_clause(field)))

    for source_field in _LIST_CLAUSE_FIELDS:
        field = contract_fields.get(source_field.value)
        clauses.extend(_clause_inputs(source_field, field, _clause_list(field)))

    return ClassificationInput(
        schema_version=snapshot.schema_version,
        input_snapshot_id=snapshot.input_snapshot_id,
        contract_id=snapshot.contract_id,
        case_id=snapshot.case_id,
        clauses=clauses,
    )
