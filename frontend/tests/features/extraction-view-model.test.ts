import { describe, expect, it } from "vitest";
import {
  correctionValue,
  fieldViewModels,
  formatFieldValue,
} from "../../src/features/extraction-review/viewModel";
import type {
  DocumentExtractionDto,
  ExtractedFieldDto,
  FieldValue,
} from "../../src/types/api";

function extractedField(field_name: string, extracted_value: FieldValue): ExtractedFieldDto {
  return {
    field_name,
    extracted_value,
    normalized_value: null,
    user_corrected_value: null,
    verification_status: "confirmed",
    confidence: extracted_value === null ? "실패" : "추출됨",
    source_evidence: { page: null, text: null },
    issue_code: extracted_value === null ? "unreadable" : null,
    failure_reason: extracted_value === null ? "읽지 못했습니다." : null,
  };
}

const ownerSharesField: ExtractedFieldDto = {
  field_name: "owner_shares",
  extracted_value: { 김하늘: "1/2", 이다온: "1/2" },
  normalized_value: null,
  user_corrected_value: null,
  verification_status: "confirmed",
  confidence: "추출됨",
  source_evidence: { page: null, text: null },
  issue_code: null,
  failure_reason: null,
};

describe("J structured field values", () => {
  it("uses Korean display labels without exposing canonical English field names", () => {
    const document: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-LABELS",
      document_type: "contract",
      warnings: [],
      fields: {
        end_date: extractedField("end_date", "2027-12-22"),
        owner_shares: ownerSharesField,
        future_field: extractedField("future_field", "확인 값"),
      },
    };

    expect(fieldViewModels([document]).map((view) => view.label)).toEqual([
      "계약 종료일",
      "소유자별 지분",
      "추가 확인 항목",
    ]);
  });

  it("uses the canonical corrected, normalized, extracted value priority", () => {
    const field = extractedField("deposit", "10000000");
    field.normalized_value = 10_000_000;
    const document: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-1",
      document_type: "contract",
      warnings: [],
      fields: { deposit: field },
    };

    expect(fieldViewModels([document])[0].formattedValue).toBe("10,000,000");
  });

  it("formats owner share mappings for review", () => {
    expect(formatFieldValue(ownerSharesField.extracted_value)).toBe(
      "김하늘:1/2, 이다온:1/2",
    );
  });

  it("parses corrected owner share mappings", () => {
    expect(
      correctionValue("김하늘:2/3, 이다온:1/3", ownerSharesField, "registry"),
    ).toEqual({ 김하늘: "2/3", 이다온: "1/3" });
  });

  it("hides deprecated v1.9 candidates and orders the four raw clause fields", () => {
    const document: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-1",
      document_type: "contract",
      warnings: [],
      fields: {
        special_clauses: extractedField("special_clauses", ["특약 1"]),
        repair_responsibility: extractedField("repair_responsibility", null),
        main_clauses: extractedField("main_clauses", ["본문 1"]),
        deposit_return_condition: extractedField("deposit_return_condition", null),
        repair_responsibility_clause: extractedField(
          "repair_responsibility_clause",
          "수리는 임대인이 부담한다.",
        ),
        deposit_return_clause: extractedField(
          "deposit_return_clause",
          "계약 종료일에 보증금을 반환한다.",
        ),
      },
    };

    const views = fieldViewModels([document]);
    expect(views.map((view) => view.field.field_name)).toEqual([
      "deposit_return_clause",
      "repair_responsibility_clause",
      "main_clauses",
      "special_clauses",
    ]);
    expect(views.map((view) => view.label)).toEqual([
      "보증금 반환 조항 원문",
      "수리·원상복구 조항 원문",
      "계약서 본문 주요 조항",
      "특약사항",
    ]);
  });

  it("keeps commas inside clause items instead of splitting the array", () => {
    const field = extractedField("main_clauses", ["기존 조항"]);
    expect(
      correctionValue(
        ["임대인은 수리하고, 임차인에게 알린다.", "두 번째 조항"],
        field,
        "contract",
      ),
    ).toEqual(["임대인은 수리하고, 임차인에게 알린다.", "두 번째 조항"]);
  });

  it("restores R11-R19 field types when a failed extraction is manually entered", () => {
    expect(correctionValue("300,000,000", extractedField("estimated_housing_value", null), "contract")).toBe(300_000_000);
    expect(correctionValue("예", extractedField("violation_building", null), "contract")).toBe(true);
    expect(correctionValue("위임장, 인감증명서", extractedField("proxy_authority_documents", null), "contract")).toEqual([
      "위임장",
      "인감증명서",
    ]);
  });

  it("distinguishes direct-confirmation fields from ordinary extraction failures", () => {
    const document: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-GUIDANCE",
      document_type: "contract",
      warnings: [],
      fields: {
        violation_building: extractedField("violation_building", null),
        account_holder: extractedField("account_holder", null),
        senior_claim_amount: extractedField("senior_claim_amount", null),
        ground_right_present: extractedField("ground_right_present", true),
      },
    };

    const views = fieldViewModels([document]);
    expect(views.find((view) => view.field.field_name === "violation_building")?.guidance).toContain("건축물대장");
    expect(views.find((view) => view.field.field_name === "account_holder")?.guidance).toContain("예금주");
    expect(views.find((view) => view.field.field_name === "senior_claim_amount")?.guidance).toContain("채권최고액");
    expect(views.find((view) => view.field.field_name === "ground_right_present")?.label).toBe("지상권 존재");
  });

  it("uses choices for guarantee eligibility and sublease authority confirmations", () => {
    const document: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-CHOICES",
      document_type: "contract",
      warnings: [],
      fields: {
        guarantee_eligibility_confirmed: extractedField("guarantee_eligibility_confirmed", null),
        lessor_sublease_authority_confirmed: extractedField("lessor_sublease_authority_confirmed", null),
      },
    };

    const views = fieldViewModels([document]);
    expect(views.map((view) => view.editor)).toEqual(["boolean-choice", "authority-choice"]);
    expect(correctionValue("true", document.fields.guarantee_eligibility_confirmed, "contract")).toBe(true);
    expect(correctionValue("false", document.fields.guarantee_eligibility_confirmed, "contract")).toBe(false);
    expect(correctionValue("owner_direct", document.fields.lessor_sublease_authority_confirmed, "contract")).toBe(true);
    expect(correctionValue("sublease_documents", document.fields.lessor_sublease_authority_confirmed, "contract")).toBe(true);
    expect(correctionValue("not_confirmed", document.fields.lessor_sublease_authority_confirmed, "contract")).toBe(false);
  });

  it("shows legacy empty proxy fields as not applicable for a direct contract", () => {
    const document: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-DIRECT",
      document_type: "contract",
      warnings: [],
      fields: {
        agent_name: extractedField("agent_name", null),
        agent_relationship: extractedField("agent_relationship", null),
        proxy_authority_documents: extractedField("proxy_authority_documents", null),
      },
    };

    const proxyViews = fieldViewModels([document]);
    expect(proxyViews.every((view) => view.field.issue_code === "not_applicable")).toBe(true);
    expect(proxyViews.every((view) => view.field.confidence === "불확실")).toBe(true);
    expect(proxyViews[1].field.failure_reason).toContain("대리인 계약 표시가 없어");
  });

  it("shows variable management fees as not stated instead of unreadable", () => {
    const document: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-VARIABLE-FEE",
      document_type: "contract",
      warnings: [],
      fields: {
        management_fee: extractedField("management_fee", null),
        management_fee_present: extractedField("management_fee_present", true),
        management_fee_items: extractedField("management_fee_items", ["전기", "수도", "공용관리비"]),
      },
    };

    const fee = fieldViewModels([document]).find((view) => view.field.field_name === "management_fee")!;
    expect(fee.field.issue_code).toBe("not_stated");
    expect(fee.field.confidence).toBe("불확실");
    expect(fee.field.failure_reason).toContain("고정 관리비 금액이 없습니다");
  });
});
