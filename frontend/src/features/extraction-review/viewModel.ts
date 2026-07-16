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
  deposit_return_condition: "보증금 반환 조건",
  issue_date: "등기 발급일",
  landlord_name: "임대인 이름",
  mortgage_present: "근저당권 존재",
  owner_names: "등기 소유자",
  property_address: "목적물 주소",
  provisional_seizure_present: "가압류 존재",
  repair_responsibility: "수리·원상복구 책임",
  rights_change_clause_present: "권리변동 제한 특약",
  seizure_present: "압류 존재",
  tenant_name: "임차인 이름",
  trust_present: "신탁등기 존재",
};

export function formatFieldValue(value: FieldValue): string {
  if (value === null) return "";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "있음" : "없음";
  if (typeof value === "number") return value.toLocaleString("ko-KR");
  return value;
}

export function fieldViewModels(documents: DocumentExtractionDto[]): FieldViewModel[] {
  return documents.flatMap((document) =>
    Object.values(document.fields).map((field) => ({
      key: `${document.document_type}:${field.field_name}`,
      document_type: document.document_type,
      label: labels[field.field_name] ?? field.field_name,
      formattedValue: formatFieldValue(field.user_corrected_value ?? field.extracted_value),
      field,
    })),
  );
}

export function correctionValue(
  rawValue: string,
  field: ExtractedFieldDto,
  documentType: DocumentType,
): Exclude<FieldValue, null> {
  const original = field.extracted_value ?? field.normalized_value;
  if (typeof original === "number") return Number(rawValue.replaceAll(",", ""));
  if (typeof original === "boolean") return rawValue === "있음" || rawValue === "true";
  if (Array.isArray(original)) {
    return rawValue.split(",").map((value) => value.trim()).filter(Boolean);
  }
  // 실패로 원래 타입을 알 수 없는 현재 canonical 필드는 account_holder(string)다.
  if (documentType === "contract" && field.field_name === "account_holder") return rawValue;
  return rawValue;
}
