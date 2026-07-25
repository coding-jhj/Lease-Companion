import type { FieldValue, FieldViewModel } from "../../types/api";
import { requiresExternalConfirmation } from "./viewModel";

const priority = [
  "property_address",
  "landlord_name",
  "owner_names",
  "deposit",
  "monthly_rent",
  "management_fee",
  "contract_payment",
  "balance_payment",
  "contract_payment_date",
  "balance_payment_date",
  "start_date",
  "end_date",
  "move_in_date",
  "special_clauses",
] as const;

const prompts: Record<string, { title: string; prompt: string }> = {
  property_address: {
    title: "계약하려는 집 주소",
    prompt: "계약서의 주소와 같나요?",
  },
  landlord_name: {
    title: "임대인 이름",
    prompt: "계약서의 임대인 이름과 같나요?",
  },
  deposit: {
    title: "보증금",
    prompt: "계약서의 보증금과 같나요?",
  },
  special_clauses: {
    title: "특약 내용",
    prompt: "계약서의 특약과 같나요?",
  },
};

export interface ReviewQueueItem {
  key: string;
  fieldName: string;
  title: string;
  prompt: string;
  view: FieldViewModel;
}

export type ReviewSection =
  | "money_direct"
  | "dispute_direct"
  | "suspected_issue"
  | "manual_or_unreadable"
  | "grouped";

export type ReviewImpact = "money" | "dispute";

export interface ReviewPlanItem extends ReviewQueueItem {
  section: ReviewSection;
  impacts: ReviewImpact[];
  reasons: string[];
  bulkConfirmAllowed: boolean;
}

const moneyFields = new Set([
  "account_holder",
  "account_number",
  "balance_payment",
  "balance_payment_date",
  "balance_payment_korean_amount",
  "bank_name",
  "contract_payment",
  "contract_payment_date",
  "contract_payment_korean_amount",
  "deposit",
  "deposit_korean_amount",
  "deposit_return_clause",
  "deposit_return_condition",
  "estimated_housing_value",
  "guarantee_eligibility_confirmed",
  "ground_right_present",
  "is_joint_ownership",
  "landlord_name",
  "management_fee",
  "management_fee_items",
  "management_fee_present",
  "monthly_rent",
  "monthly_rent_korean_amount",
  "mortgage_present",
  "owner_names",
  "owner_shares",
  "provisional_seizure_present",
  "rights_change_clause_present",
  "seizure_present",
  "senior_claim_amount",
  "trust_present",
]);

const disputeFields = new Set([
  "agent_name",
  "agent_relationship",
  "building_use",
  "deposit_return_clause",
  "deposit_return_condition",
  "end_date",
  "is_joint_ownership",
  "landlord_name",
  "lessor_sublease_authority_confirmed",
  "main_clauses",
  "management_fee",
  "management_fee_items",
  "management_fee_present",
  "move_in_date",
  "owner_names",
  "owner_shares",
  "property_address",
  "proxy_authority_documents",
  "repair_responsibility",
  "repair_responsibility_clause",
  "special_clauses",
  "special_clauses_present",
  "start_date",
  "tenant_name",
  "violation_building",
]);

const amountPairs = [
  ["deposit", "deposit_korean_amount"],
  ["monthly_rent", "monthly_rent_korean_amount"],
  ["contract_payment", "contract_payment_korean_amount"],
  ["balance_payment", "balance_payment_korean_amount"],
] as const;

const sectionOrder: Record<ReviewSection, number> = {
  money_direct: 0,
  dispute_direct: 1,
  suspected_issue: 2,
  manual_or_unreadable: 3,
  grouped: 4,
};

function effectiveValue(view: FieldViewModel): FieldValue {
  return view.field.user_corrected_value
    ?? view.field.normalized_value
    ?? view.field.extracted_value;
}

function hasValue(value: FieldValue): boolean {
  if (value === null) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "string") return value.trim().length > 0;
  return true;
}

function normalizedText(value: FieldValue): string {
  if (Array.isArray(value)) return value.map((item) => normalizedText(item)).join("|");
  if (value === null) return "";
  return String(value).normalize("NFKC").replace(/\s+/g, "").toLocaleLowerCase("ko-KR");
}

function dateValue(value: FieldValue): number | null {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const parsed = Date.parse(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed)) return null;
  return new Date(parsed).toISOString().slice(0, 10) === value ? parsed : null;
}

function hasSourceEvidence(view: FieldViewModel): boolean {
  return view.field.source_evidence.page !== null
    && Boolean(view.field.source_evidence.text?.trim());
}

function addReason(
  reasonsByKey: Map<string, string[]>,
  views: Array<FieldViewModel | undefined>,
  reason: string,
) {
  for (const view of views) {
    if (!view) continue;
    const reasons = reasonsByKey.get(view.key) ?? [];
    if (!reasons.includes(reason)) reasons.push(reason);
    reasonsByKey.set(view.key, reasons);
  }
}

function comparisonReasons(fields: FieldViewModel[]): Map<string, string[]> {
  const reasonsByKey = new Map<string, string[]>();
  const byKey = new Map(fields.map((view) => [view.key, view]));

  const contractAddress = byKey.get("contract:property_address");
  const registryAddress = byKey.get("registry:property_address");
  if (
    contractAddress
    && registryAddress
    && hasValue(effectiveValue(contractAddress))
    && hasValue(effectiveValue(registryAddress))
    && normalizedText(effectiveValue(contractAddress)) !== normalizedText(effectiveValue(registryAddress))
  ) {
    addReason(
      reasonsByKey,
      [contractAddress, registryAddress],
      "계약서와 등기사항증명서의 주소가 다르게 읽혔습니다.",
    );
  }

  const landlord = byKey.get("contract:landlord_name");
  const owners = byKey.get("registry:owner_names");
  if (landlord && owners && hasValue(effectiveValue(landlord)) && hasValue(effectiveValue(owners))) {
    const landlordName = normalizedText(effectiveValue(landlord));
    const ownerValue = effectiveValue(owners);
    const ownerNames = Array.isArray(ownerValue)
      ? ownerValue.map((name) => normalizedText(name))
      : [normalizedText(ownerValue)];
    if (!ownerNames.includes(landlordName)) {
      addReason(
        reasonsByKey,
        [landlord, owners],
        "계약서 임대인과 등기 소유자 이름이 다르게 읽혔습니다.",
      );
    }
  }

  for (const [numericName, koreanName] of amountPairs) {
    const numeric = byKey.get(`contract:${numericName}`);
    const korean = byKey.get(`contract:${koreanName}`);
    const numericValue = numeric ? effectiveValue(numeric) : null;
    const koreanValue = korean ? effectiveValue(korean) : null;
    if (
      numeric
      && korean
      && typeof numericValue === "number"
      && typeof koreanValue === "number"
      && numericValue !== koreanValue
    ) {
      addReason(
        reasonsByKey,
        [numeric, korean],
        "숫자 금액과 한글 금액이 다르게 읽혔습니다.",
      );
    }
  }

  const startDate = byKey.get("contract:start_date");
  const endDate = byKey.get("contract:end_date");
  const start = startDate ? dateValue(effectiveValue(startDate)) : null;
  const end = endDate ? dateValue(effectiveValue(endDate)) : null;
  if (start !== null && end !== null && start > end) {
    addReason(
      reasonsByKey,
      [startDate, endDate],
      "계약 시작일이 종료일보다 늦게 읽혔습니다.",
    );
  }

  const moveInDate = byKey.get("contract:move_in_date");
  const moveIn = moveInDate ? dateValue(effectiveValue(moveInDate)) : null;
  if (
    moveIn !== null
    && ((start !== null && moveIn < start) || (end !== null && moveIn > end))
  ) {
    addReason(
      reasonsByKey,
      [startDate, moveInDate, endDate],
      "입주일이 계약기간 밖으로 읽혔습니다.",
    );
  }

  const contractPaymentDate = byKey.get("contract:contract_payment_date");
  const balancePaymentDate = byKey.get("contract:balance_payment_date");
  const contractPayment = contractPaymentDate
    ? dateValue(effectiveValue(contractPaymentDate))
    : null;
  const balancePayment = balancePaymentDate
    ? dateValue(effectiveValue(balancePaymentDate))
    : null;
  if (
    contractPayment !== null
    && balancePayment !== null
    && contractPayment > balancePayment
  ) {
    addReason(
      reasonsByKey,
      [contractPaymentDate, balancePaymentDate],
      "계약금 지급일이 잔금 지급일보다 늦게 읽혔습니다.",
    );
  }

  return reasonsByKey;
}

function impactsFor(fieldName: string): ReviewImpact[] {
  const impacts: ReviewImpact[] = [];
  if (moneyFields.has(fieldName)) impacts.push("money");
  if (disputeFields.has(fieldName)) impacts.push("dispute");
  return impacts;
}

function fieldReasons(view: FieldViewModel): string[] {
  const reasons: string[] = [];
  switch (view.field.issue_code) {
    case "unreadable":
      reasons.push("글자를 읽지 못했습니다.");
      break;
    case "parse_failed":
      reasons.push("내용 형식을 해석하지 못했습니다.");
      break;
    case "not_stated":
      reasons.push("문서에 내용이 적혀 있지 않습니다.");
      break;
    case "ambiguous":
      reasons.push("추출 내용이 불확실합니다.");
      break;
  }
  if (view.field.issue_code === null && view.field.confidence !== "추출됨") {
    reasons.push("자동 추출 신뢰도가 낮아 직접 확인해야 합니다.");
  }
  if (requiresExternalConfirmation(view)) {
    reasons.push("다른 자료에서 직접 확인해야 합니다.");
  }
  if (
    view.field.verification_status === "corrected"
    || view.field.user_corrected_value !== null
  ) {
    reasons.push("사용자가 이전에 수정한 값입니다.");
  }
  if (view.field.verification_status === "unresolved") {
    reasons.push("사용자가 아직 확인하지 못했습니다.");
  }
  if (hasValue(effectiveValue(view)) && !hasSourceEvidence(view)) {
    reasons.push("원문 위치 정보가 없어 문서에서 직접 대조해야 합니다.");
  }
  return reasons;
}

function sectionFor(
  view: FieldViewModel,
  impacts: ReviewImpact[],
  reasons: string[],
): ReviewSection | null {
  if (view.field.issue_code === "not_applicable") return null;
  if (
    view.field.issue_code === "unreadable"
    || view.field.issue_code === "parse_failed"
    || requiresExternalConfirmation(view)
  ) {
    return "manual_or_unreadable";
  }
  if (impacts.includes("money")) return "money_direct";
  if (impacts.includes("dispute")) return "dispute_direct";
  if (reasons.length > 0 || view.field.issue_code !== null) return "suspected_issue";
  return "grouped";
}

export function buildReviewQueue(fields: FieldViewModel[]): ReviewQueueItem[] {
  const uniqueFields = fields.filter((field, index) =>
    fields.findIndex(
      (candidate) => candidate.key === field.key,
    ) === index,
  );
  const fieldNameCounts = new Map<string, number>();
  for (const field of uniqueFields) {
    fieldNameCounts.set(field.field.field_name, (fieldNameCounts.get(field.field.field_name) ?? 0) + 1);
  }
  const priorityIndex = new Map<string, number>(
    priority.map((fieldName, index) => [fieldName, index]),
  );

  return uniqueFields
    .map((view, index) => ({ view, index }))
    .sort(({ view: left, index: leftIndex }, { view: right, index: rightIndex }) => {
      const leftPriority = priorityIndex.get(left.field.field_name);
      const rightPriority = priorityIndex.get(right.field.field_name);
      if (leftPriority === undefined && rightPriority === undefined) return leftIndex - rightIndex;
      if (leftPriority === undefined) return 1;
      if (rightPriority === undefined) return -1;
      return leftPriority - rightPriority;
    })
    .map(({ view }) => {
      const fieldName = view.field.field_name;
      const mapped = prompts[fieldName];
      const documentLabel = view.document_type === "registry" ? "등기사항증명서" : "계약서";
      const needsDocumentLabel = (fieldNameCounts.get(fieldName) ?? 0) > 1;
      const baseTitle = mapped?.title ?? view.label;
      return {
        key: view.key,
        fieldName,
        title: needsDocumentLabel ? `${documentLabel} ${baseTitle}` : baseTitle,
        prompt: needsDocumentLabel
          ? `${documentLabel}에서 읽은 ${baseTitle} 내용이 맞나요?`
          : mapped?.prompt ?? `${view.label} 내용이 계약서와 같나요?`,
        view,
      };
    });
}

export function buildReviewPlan(fields: FieldViewModel[]): ReviewPlanItem[] {
  const queue = buildReviewQueue(fields);
  const comparisonReasonByKey = comparisonReasons(queue.map((item) => item.view));

  return queue
    .map((item, index) => {
      const impacts = impactsFor(item.fieldName);
      const reasons = [
        ...fieldReasons(item.view),
        ...(comparisonReasonByKey.get(item.key) ?? []),
        ...(impacts.includes("money")
          ? ["금액 지급이나 보증금 회수와 연결된 내용입니다."]
          : []),
        ...(impacts.includes("dispute")
          ? ["계약 조건이나 책임 범위를 직접 확인할 내용입니다."]
          : []),
      ].filter((reason, reasonIndex, allReasons) => allReasons.indexOf(reason) === reasonIndex);
      const section = sectionFor(item.view, impacts, reasons);
      if (section === null) return null;
      return {
        ...item,
        section,
        impacts,
        reasons,
        bulkConfirmAllowed: section === "grouped"
          && item.view.field.verification_status === "unverified"
          && item.view.field.user_corrected_value === null,
        index,
      };
    })
    .filter((item): item is ReviewPlanItem & { index: number } => item !== null)
    .sort((left, right) => (
      sectionOrder[left.section] - sectionOrder[right.section]
      || left.index - right.index
    ))
    .map(({ index: _index, ...item }) => item);
}
