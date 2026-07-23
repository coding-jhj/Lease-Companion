import type { FieldViewModel } from "../../types/api";

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
