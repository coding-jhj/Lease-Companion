import type {
  DocumentExtractionDto,
  DocumentType,
  ExtractedFieldDto,
  FieldValue,
  FieldViewModel,
} from "../../types/api";

const labels: Record<string, string> = {
  account_holder: "입금 계좌 예금주",
  deposit: "보증금",
  deposit_return_clause: "보증금 반환 조항 원문",
  deposit_return_condition: "보증금 반환 조건",
  issue_date: "등기 발급일",
  landlord_name: "임대인 이름",
  main_clauses: "계약서 본문 주요 조항",
  mortgage_present: "근저당권 존재",
  owner_names: "등기 소유자",
  property_address: "목적물 주소",
  provisional_seizure_present: "가압류 존재",
  repair_responsibility: "수리·원상복구 책임",
  repair_responsibility_clause: "수리·원상복구 조항 원문",
  rights_change_clause_present: "권리변동 제한 특약",
  seizure_present: "압류 존재",
  special_clauses: "특약사항",
  tenant_name: "임차인 이름",
  trust_present: "신탁등기 존재",
};

const clauseListFields = new Set(["main_clauses", "special_clauses"]);

const clauseDisplayOrder: Record<string, number> = {
  deposit_return_clause: 0,
  deposit_return_condition: 0,
  repair_responsibility_clause: 1,
  repair_responsibility: 1,
  main_clauses: 2,
  special_clauses: 3,
};

const legacyCandidateByClause: Record<string, string> = {
  deposit_return_clause: "deposit_return_condition",
  repair_responsibility_clause: "repair_responsibility",
};

const clauseByLegacyCandidate = Object.fromEntries(
  Object.entries(legacyCandidateByClause).map(([clause, legacy]) => [legacy, clause]),
);

function effectiveValue(field: ExtractedFieldDto): FieldValue {
  return field.user_corrected_value ?? field.normalized_value ?? field.extracted_value;
}

function hasDisplayValue(field: ExtractedFieldDto | undefined): boolean {
  if (!field) return false;
  const value = effectiveValue(field);
  if (value === null) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "string") return value.trim().length > 0;
  return true;
}

function visibleFields(document: DocumentExtractionDto): ExtractedFieldDto[] {
  const fields = Object.values(document.fields);
  if (document.document_type !== "contract") return fields;

  return fields
    .filter((field) => {
      const clauseName = clauseByLegacyCandidate[field.field_name];
      if (clauseName) {
        if (document.schema_version === "1.9.0") return false;
        return !hasDisplayValue(document.fields[clauseName]);
      }

      const legacyName = legacyCandidateByClause[field.field_name];
      if (document.schema_version === "1.8.0" && legacyName) {
        return hasDisplayValue(field) || !hasDisplayValue(document.fields[legacyName]);
      }
      return true;
    })
    .map((field, index) => ({ field, index }))
    .sort((left, right) => {
      const leftPriority = clauseDisplayOrder[left.field.field_name];
      const rightPriority = clauseDisplayOrder[right.field.field_name];
      if (leftPriority === undefined && rightPriority === undefined) return left.index - right.index;
      if (leftPriority === undefined) return 1;
      if (rightPriority === undefined) return -1;
      return leftPriority - rightPriority || left.index - right.index;
    })
    .map(({ field }) => field);
}

export function formatFieldValue(value: FieldValue): string {
  if (value === null) return "";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "있음" : "없음";
  if (typeof value === "number") return value.toLocaleString("ko-KR");
  if (typeof value === "object") {
    return Object.entries(value).map(([key, item]) => key + ":" + item).join(", ");
  }
  return value;
}

export function fieldViewModels(documents: DocumentExtractionDto[]): FieldViewModel[] {
  return documents.flatMap((document) =>
    visibleFields(document).map((field) => ({
      key: document.document_type + ":" + field.field_name,
      document_type: document.document_type,
      label: labels[field.field_name] ?? field.field_name,
      formattedValue: formatFieldValue(effectiveValue(field)),
      editor: clauseListFields.has(field.field_name) ? "clause-list" as const : "scalar" as const,
      field,
    })),
  );
}

export function clauseValues(field: ExtractedFieldDto): string[] {
  const value = effectiveValue(field);
  return Array.isArray(value) ? value : [];
}

export function correctionValue(
  rawValue: string | string[],
  field: ExtractedFieldDto,
  documentType: DocumentType,
): Exclude<FieldValue, null> {
  if (clauseListFields.has(field.field_name)) {
    const items = Array.isArray(rawValue) ? rawValue : [rawValue];
    return items.map((value) => value.trim()).filter(Boolean);
  }

  const scalarValue = Array.isArray(rawValue) ? rawValue.join(", ") : rawValue;
  const original = field.normalized_value ?? field.extracted_value;
  if (typeof original === "number") return Number(scalarValue.replaceAll(",", ""));
  if (typeof original === "boolean") return scalarValue === "있음" || scalarValue === "true";
  if (Array.isArray(original)) {
    return scalarValue.split(",").map((value) => value.trim()).filter(Boolean);
  }
  if (typeof original === "object" && original !== null) {
    return Object.fromEntries(
      scalarValue
        .split(",")
        .map((entry) => entry.split(":"))
        .filter((parts) => parts.length >= 2)
        .map(([key, ...parts]) => [key.trim(), parts.join(":").trim()]),
    );
  }
  // 실패로 원래 타입을 알 수 없는 현재 canonical 필드는 account_holder(string)다.
  if (documentType === "contract" && field.field_name === "account_holder") return scalarValue;
  return scalarValue;
}
