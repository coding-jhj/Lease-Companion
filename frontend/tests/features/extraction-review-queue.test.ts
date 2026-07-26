import { describe, expect, it } from "vitest";
import {
  buildReviewPlan,
  buildReviewQueue,
} from "../../src/features/extraction-review/reviewQueue";
import type {
  ExtractedFieldDto,
  FieldValue,
  FieldViewModel,
} from "../../src/types/api";

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

function reviewField(
  fieldName: string,
  options: {
    value?: FieldValue;
    documentType?: "contract" | "registry";
    issueCode?: ExtractedFieldDto["issue_code"];
    confidence?: ExtractedFieldDto["confidence"];
    verificationStatus?: ExtractedFieldDto["verification_status"];
    correctedValue?: FieldValue;
    hasEvidence?: boolean;
  } = {},
): FieldViewModel {
  const value = Object.hasOwn(options, "value") ? options.value! : "확인 값";
  const documentType = options.documentType ?? "contract";
  return {
    key: `${documentType}:${fieldName}`,
    document_type: documentType,
    label: `${fieldName} 라벨`,
    formattedValue: value === null ? "" : String(value),
    editor: "scalar",
    guidance: null,
    field: {
      field_name: fieldName,
      extracted_value: value,
      normalized_value: value,
      user_corrected_value: options.correctedValue ?? null,
      verification_status: options.verificationStatus ?? "unverified",
      confidence: options.confidence ?? (value === null ? "실패" : "추출됨"),
      source_evidence: options.hasEvidence === false
        ? { page: null, text: null }
        : { page: 1, text: "문서 원문" },
      issue_code: options.issueCode ?? null,
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

describe("buildReviewPlan", () => {
  it("places fields into five sections and excludes not-applicable fields", () => {
    const plan = buildReviewPlan([
      reviewField("issue_date"),
      reviewField("future_field", {
        confidence: "불확실",
        issueCode: "ambiguous",
      }),
      reviewField("repair_responsibility", { confidence: "불확실" }),
      reviewField("deposit"),
      reviewField("owner_shares", {
        value: null,
        issueCode: "unreadable",
      }),
      reviewField("violation_building", {
        value: null,
        issueCode: "not_stated",
      }),
      reviewField("agent_name", {
        value: null,
        issueCode: "not_applicable",
      }),
    ]);

    expect(plan.map((item) => [item.fieldName, item.section])).toEqual([
      ["deposit", "money_direct"],
      ["repair_responsibility", "dispute_direct"],
      ["future_field", "suspected_issue"],
      ["owner_shares", "manual_or_unreadable"],
      ["violation_building", "manual_or_unreadable"],
      ["issue_date", "grouped"],
    ]);
    expect(plan.find((item) => item.fieldName === "deposit")?.impacts).toEqual(["money"]);
    expect(plan.find((item) => item.fieldName === "repair_responsibility")?.impacts).toEqual(["dispute"]);
    expect(plan.find((item) => item.fieldName === "violation_building")?.reasons)
      .toContain("다른 자료에서 직접 확인해 주세요.");
    expect(plan.some((item) => item.fieldName === "agent_name")).toBe(false);
  });

  it("keeps core money fields in their own sections but allows bulk confirmation", () => {
    const plan = buildReviewPlan([
      reviewField("deposit", { value: 300_000_000 }),
      reviewField("account_number", { value: "123-456" }),
      reviewField("special_clauses", { value: "특약 하나" }),
      reviewField("management_fee_items", { value: "수도" }),
    ]);

    // 핵심 항목은 여전히 개별 카드로 남아 "직접 고칠게요"를 쓸 수 있고,
    // 고칠 내용이 없으면 구역 단위 묶음 확인에 포함된다.
    for (const fieldName of ["deposit", "account_number", "special_clauses"]) {
      expect(plan.find((item) => item.fieldName === fieldName)?.section)
        .not.toBe("grouped");
      expect(plan.find((item) => item.fieldName === fieldName)?.bulkConfirmAllowed)
        .toBe(true);
    }
    expect(plan.find((item) => item.fieldName === "management_fee_items")).toMatchObject({
      section: "grouped",
      bulkConfirmAllowed: true,
    });
  });

  it("does not compare values across documents and keeps each document field separate", () => {
    const plan = buildReviewPlan([
      reviewField("property_address", { value: "서울시 101호" }),
      reviewField("property_address", {
        value: "서울시 102호",
        documentType: "registry",
      }),
      reviewField("landlord_name", { value: "김임대" }),
      reviewField("owner_names", {
        value: ["박소유"],
        documentType: "registry",
      }),
      reviewField("deposit", { value: 100_000_000 }),
      reviewField("deposit_korean_amount", { value: 110_000_000 }),
      reviewField("start_date", { value: "2027-12-31" }),
      reviewField("end_date", { value: "2027-01-01" }),
    ]);

    expect(plan).toHaveLength(8);
    expect(new Set(plan.map((item) => item.key)).size).toBe(8);
    expect(plan.filter((item) => item.fieldName === "property_address"))
      .toHaveLength(2);
    expect(plan.filter((item) => item.fieldName === "property_address")
      .every((item) => item.section === "dispute_direct")).toBe(true);
    expect(plan.find((item) => item.fieldName === "landlord_name")).toMatchObject({
      section: "money_direct",
      impacts: ["money", "dispute"],
    });
    // 문서 간 값 비교는 6단계 규칙 엔진 전용이다. 5단계는 어떤 불일치도 주장하지 않는다.
    expect(plan.flatMap((item) => item.reasons)
      .some((reason) => reason.includes("다르"))).toBe(false);
  });

  it("allows bulk confirmation only for unreviewed fields the user has not corrected", () => {
    const exactDuplicate = reviewField("issue_date");
    const plan = buildReviewPlan([
      exactDuplicate,
      exactDuplicate,
      reviewField("future_without_evidence", { hasEvidence: false }),
      reviewField("future_failed", {
        value: null,
        confidence: "실패",
        hasEvidence: false,
      }),
      reviewField("future_corrected", {
        correctedValue: "사용자 수정",
        verificationStatus: "corrected",
      }),
      reviewField("future_unresolved", {
        issueCode: "not_stated",
        verificationStatus: "unresolved",
      }),
    ]);

    expect(plan.filter((item) => item.key === "contract:issue_date")).toHaveLength(1);
    expect(plan.find((item) => item.fieldName === "issue_date")).toMatchObject({
      section: "grouped",
      bulkConfirmAllowed: true,
    });
    // 원문 위치(page·text)는 현재 추출기가 거의 채우지 않아 분류 신호로 쓰지 않는다.
    expect(plan.find((item) => item.fieldName === "future_without_evidence")).toMatchObject({
      section: "grouped",
      bulkConfirmAllowed: true,
    });
    expect(plan.find((item) => item.fieldName === "future_failed")).toMatchObject({
      section: "suspected_issue",
      bulkConfirmAllowed: true,
    });
    expect(plan.find((item) => item.fieldName === "future_corrected")).toMatchObject({
      section: "grouped",
      bulkConfirmAllowed: false,
    });
    expect(plan.find((item) => item.fieldName === "future_unresolved")?.bulkConfirmAllowed)
      .toBe(false);
  });
});
