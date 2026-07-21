import type {
  DocumentExtractionDto,
  DocumentType,
  ExtractedFieldDto,
  FieldValue,
  FieldViewModel,
} from "../../types/api";

const labels: Record<string, string> = {
  account_holder: "입금 계좌 예금주",
  account_number: "입금 계좌번호",
  bank_name: "입금 은행",
  agent_name: "대리인 이름",
  agent_relationship: "대리인과 임대인의 관계",
  balance_payment: "잔금",
  balance_payment_date: "잔금 지급일",
  balance_payment_korean_amount: "잔금 한글 표기 금액",
  building_use: "건축물 용도",
  contract_payment: "계약금",
  contract_payment_date: "계약금 지급일",
  contract_payment_korean_amount: "계약금 한글 표기 금액",
  deposit: "보증금",
  deposit_korean_amount: "보증금 한글 표기 금액",
  deposit_return_clause: "보증금 반환 조항 원문",
  deposit_return_condition: "보증금 반환 조건",
  end_date: "계약 종료일",
  estimated_housing_value: "확인된 주택가치",
  guarantee_eligibility_confirmed: "전세보증 가입 요건 확인",
  ground_right_present: "지상권 존재",
  is_joint_ownership: "공동소유 여부",
  issue_date: "등기 발급일",
  landlord_name: "임대인 이름",
  lessor_sublease_authority_confirmed: "임대·전대 권한 확인",
  main_clauses: "계약서 본문 주요 조항",
  mortgage_present: "근저당권 존재",
  management_fee: "관리비 금액",
  management_fee_items: "관리비 포함 항목",
  management_fee_present: "관리비 존재",
  monthly_rent: "월세",
  monthly_rent_korean_amount: "월세 한글 표기 금액",
  move_in_date: "입주일",
  owner_names: "등기 소유자",
  owner_shares: "소유자별 지분",
  property_address: "목적물 주소",
  provisional_seizure_present: "가압류 존재",
  proxy_authority_documents: "대리권 확인 서류",
  repair_responsibility: "수리·원상복구 책임",
  repair_responsibility_clause: "수리·원상복구 조항 원문",
  rights_change_clause_present: "권리변동 제한 특약",
  seizure_present: "압류 존재",
  senior_claim_amount: "선순위 권리·채권 합계",
  special_clauses: "특약사항",
  special_clauses_present: "특약 존재 여부",
  start_date: "계약 시작일",
  tenant_name: "임차인 이름",
  trust_present: "신탁등기 존재",
  violation_building: "위반건축물 표시",
};

const reviewGuidance: Record<string, string> = {
  account_holder: "계좌번호만 있고 예금주가 없으면 송금 전에 임대인 본인 명의인지 직접 확인하세요.",
  agent_relationship: "대리계약일 때만 입력합니다. 임대인이 직접 계약했다면 비워둘 수 있습니다.",
  proxy_authority_documents: "대리계약일 때 위임장·인감증명서 등 실제 확인한 서류만 입력하세요.",
  building_use: "계약서의 구조·용도 칸과 최신 건축물대장을 함께 확인하세요.",
  contract_payment_date: "계약시에 지급으로만 적혀 있다면 계약 체결일과 같은지 확인하세요.",
  estimated_housing_value: "시세 자료의 금액과 기준일을 직접 확인해 입력하는 항목입니다.",
  guarantee_eligibility_confirmed: "보증기관의 현재 가입 요건과 신청 기한을 확인한 뒤 입력하세요.",
  ground_right_present: "등기사항증명서 을구의 지상권설정 여부입니다. 존재 여부만 표시하며 금액으로 환산하지 않습니다.",
  lessor_sublease_authority_confirmed: "소유권 또는 적법한 전대 동의 서류를 확인한 뒤 입력하세요.",
  management_fee: "사용량·세대수 비례 관리비는 고정 금액이 없을 수 있으므로 산정 방식과 포함 항목을 확인하세요.",
  move_in_date: "명시된 입주일이 없으면 임차주택 인도일이 실제 입주일과 같은지 확인하세요.",
  senior_claim_amount: "채권최고액·실제 채무액과 임차보증금보다 앞서는 순위를 확인한 뒤 입력하세요.",
  violation_building: "최신 건축물대장의 위반건축물 표시를 직접 확인하는 항목입니다.",
};

const numericFields = new Set([
  "balance_payment", "contract_payment", "deposit", "estimated_housing_value",
  "management_fee", "monthly_rent", "senior_claim_amount",
]);
const booleanFields = new Set([
  "guarantee_eligibility_confirmed", "lessor_sublease_authority_confirmed",
  "management_fee_present", "mortgage_present", "provisional_seizure_present",
  "ground_right_present",
  "rights_change_clause_present", "seizure_present", "special_clauses_present",
  "trust_present", "violation_building",
]);
const listFields = new Set([
  "main_clauses", "management_fee_items", "owner_names", "proxy_authority_documents", "special_clauses",
]);

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
      label: labels[field.field_name] ?? "추가 확인 항목",
      formattedValue: formatFieldValue(effectiveValue(field)),
      editor: clauseListFields.has(field.field_name) ? "clause-list" as const : "scalar" as const,
      guidance: reviewGuidance[field.field_name] ?? null,
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
  if (numericFields.has(field.field_name)) return Number(scalarValue.replaceAll(",", ""));
  if (booleanFields.has(field.field_name)) return scalarValue === "있음" || scalarValue === "true" || scalarValue === "예";
  if (listFields.has(field.field_name)) return scalarValue.split(",").map((value) => value.trim()).filter(Boolean);
  // 판독 실패 필드는 canonical field_name으로 타입을 복원한다.
  if (documentType === "contract" && field.field_name === "account_holder") return scalarValue;
  return scalarValue;
}
