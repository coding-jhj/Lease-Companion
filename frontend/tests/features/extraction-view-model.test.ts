import { describe, expect, it } from "vitest";
import {
  correctionValue,
  formatFieldValue,
} from "../../src/features/extraction-review/viewModel";
import type { ExtractedFieldDto } from "../../src/types/api";

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
});
