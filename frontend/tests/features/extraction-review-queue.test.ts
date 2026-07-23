import { describe, expect, it } from "vitest";
import { buildReviewQueue } from "../../src/features/extraction-review/reviewQueue";
import type { FieldViewModel } from "../../src/types/api";

function field(
  fieldName: string,
  label = `${fieldName} 라벨`,
  documentType: "contract" | "registry" = "contract",
): FieldViewModel {
  return {
    key: `${documentType}:${fieldName}`,
    document_type: documentType,
    label,
    formattedValue: "",
    editor: "scalar",
    guidance: null,
    field: {
      field_name: fieldName,
      extracted_value: null,
      normalized_value: null,
      user_corrected_value: null,
      verification_status: "unverified",
      confidence: "실패",
      source_evidence: { page: null, text: null },
      issue_code: "unreadable",
      failure_reason: null,
    },
  };
}

describe("buildReviewQueue", () => {
  it("places available priority fields first and keeps remaining fields in input order", () => {
    const fields = [
      field("future_field", "추가 항목"),
      field("special_clauses"),
      field("management_fee"),
      field("landlord_name"),
      field("deposit"),
      field("balance_payment_date"),
      field("property_address"),
      field("start_date"),
      field("another_field", "다른 항목"),
    ];

    expect(buildReviewQueue(fields).map((item) => item.fieldName)).toEqual([
      "property_address",
      "landlord_name",
      "deposit",
      "management_fee",
      "balance_payment_date",
      "start_date",
      "special_clauses",
      "future_field",
      "another_field",
    ]);
  });

  it("keeps document-specific fields and skips only an exact view key duplicate", () => {
    const fields = [
      field("deposit", "첫 보증금"),
      field("deposit", "중복 보증금", "registry"),
      field("deposit", "진짜 중복 보증금"),
      field("special_clauses"),
      field("future_field", "추가 항목"),
    ];

    expect(buildReviewQueue(fields)).toMatchObject([
      {
        key: "contract:deposit",
        fieldName: "deposit",
        title: "계약서 보증금",
        prompt: "계약서에서 읽은 보증금 내용이 맞나요?",
        view: fields[0],
      },
      {
        key: "registry:deposit",
        fieldName: "deposit",
        title: "등기사항증명서 보증금",
        prompt: "등기사항증명서에서 읽은 보증금 내용이 맞나요?",
        view: fields[1],
      },
      {
        fieldName: "special_clauses",
        title: "특약 내용",
        prompt: "계약서의 특약과 같나요?",
      },
      {
        fieldName: "future_field",
        title: "추가 항목",
        prompt: "추가 항목 내용이 계약서와 같나요?",
      },
    ]);
  });
});
