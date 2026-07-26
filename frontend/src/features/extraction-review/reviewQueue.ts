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

// 값이 틀리면 뒤 판정이 전부 흔들리는 항목. 추출 품질과 무관하게 개별 확인을 받는다.
const coreFields = new Set([
  "account_holder",
  "account_number",
  "balance_payment",
  "bank_name",
  "contract_payment",
  "deposit",
  "end_date",
  "landlord_name",
  "monthly_rent",
  "property_address",
  "special_clauses",
  "start_date",
]);

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
      reasons.push("글자를 읽지 못했어요.");
      break;
    case "parse_failed":
      reasons.push("내용 형태를 알아보지 못했어요.");
      break;
    case "not_stated":
      reasons.push("문서에 안 적혀 있어요.");
      break;
    case "ambiguous":
      reasons.push("읽은 내용이 분명하지 않아요.");
      break;
  }
  if (view.field.issue_code === null && view.field.confidence !== "추출됨") {
    reasons.push("자동으로 읽은 값이라 한 번 봐 주세요.");
  }
  if (requiresExternalConfirmation(view)) {
    reasons.push("다른 자료에서 직접 확인해 주세요.");
  }
  if (
    view.field.verification_status === "corrected"
    || view.field.user_corrected_value !== null
  ) {
    reasons.push("전에 직접 고친 값이에요.");
  }
  if (view.field.verification_status === "unresolved") {
    reasons.push("아직 확인하지 못한 내용이에요.");
  }
  return reasons;
}

function hasQualityIssue(view: FieldViewModel): boolean {
  return view.field.issue_code !== null
    || view.field.confidence !== "추출됨"
    || !hasValue(effectiveValue(view));
}

function sectionFor(view: FieldViewModel, impacts: ReviewImpact[]): ReviewSection | null {
  if (view.field.issue_code === "not_applicable") return null;
  if (
    view.field.issue_code === "unreadable"
    || view.field.issue_code === "parse_failed"
    || requiresExternalConfirmation(view)
  ) {
    return "manual_or_unreadable";
  }
  // 빠졌거나 뜻이 분명하지 않은 값은 돈·책임 분류보다 먼저 "다시 봐야 할 내용"으로 모은다.
  if (view.field.issue_code === "not_stated" || view.field.issue_code === "ambiguous") {
    return "suspected_issue";
  }
  // 잘 읽힌 일반 항목은 묶음 확인으로 보내고, 핵심 항목과 품질 이슈만 개별 카드로 남긴다.
  if (!hasQualityIssue(view) && !coreFields.has(view.field.field_name)) return "grouped";
  if (impacts.includes("money")) return "money_direct";
  if (impacts.includes("dispute")) return "dispute_direct";
  return "suspected_issue";
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

  return queue
    .map((item, index) => {
      const impacts = impactsFor(item.fieldName);
      const reasons = fieldReasons(item.view);
      const section = sectionFor(item.view, impacts);
      if (section === null) return null;
      return {
        ...item,
        section,
        impacts,
        reasons,
        // 개별 확인 버튼을 없앴으므로 아직 확인하지 않은 항목은 모두 묶음 확인 대상이다.
        // 그렇지 않으면 확인할 방법이 없는 항목이 생겨 구역을 끝낼 수 없다.
        // 이미 고치거나 확인한 항목은 verification_status로 걸러진다.
        bulkConfirmAllowed: item.view.field.verification_status === "unverified",
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
