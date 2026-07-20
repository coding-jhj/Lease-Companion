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
});
