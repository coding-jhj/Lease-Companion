import { describe, expect, it } from "vitest";
import {
  cleanClauseLine,
  correctionValue,
  extractionStatusMeta,
  fieldViewModels,
  formatClauseText,
  formatFieldValue,
  reviewStatusMeta,
  splitClauseText,
  splitClausesForDisplay,
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
  it("distinguishes extraction issues instead of labeling every failed-confidence field unreadable", () => {
    const document: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-STATUS",
      document_type: "contract",
      warnings: [],
      fields: {
        unreadable: {
          ...extractedField("owner_shares", null),
          issue_code: "unreadable",
        },
        parse_failed: {
          ...extractedField("deposit", null),
          issue_code: "parse_failed",
        },
        not_stated: {
          ...extractedField("account_holder", null),
          issue_code: "not_stated",
        },
        not_applicable: {
          ...extractedField("agent_name", null),
          issue_code: "not_applicable",
        },
        external_confirmation: {
          ...extractedField("violation_building", null),
          issue_code: "not_stated",
        },
        ambiguous: {
          ...extractedField("building_use", null),
          confidence: "불확실",
          issue_code: "ambiguous",
        },
      },
    };

    const statusByField = Object.fromEntries(
      fieldViewModels([document]).map((view) => [
        view.field.field_name,
        extractionStatusMeta(view).label,
      ]),
    );

    expect(statusByField).toMatchObject({
      owner_shares: "글자를 읽지 못함",
      deposit: "내용 형식을 해석하지 못함",
      account_holder: "문서에 적혀 있지 않음",
      agent_name: "현재 계약에 해당하지 않음",
      violation_building: "다른 자료에서 확인 필요",
      building_use: "내용이 불확실함",
    });
  });

  it("shows user review state before extraction state", () => {
    const document: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-REVIEW-STATUS",
      document_type: "registry",
      warnings: [],
      fields: {
        owner_shares: {
          ...extractedField("owner_shares", null),
          verification_status: "unresolved",
        },
      },
    };
    const view = fieldViewModels([document])[0];

    expect(reviewStatusMeta(view, { reviewed: true, unresolved: false }).label)
      .toBe("확인하지 못함");
    expect(reviewStatusMeta(view, { reviewed: false, unresolved: true }).label)
      .toBe("확인하지 못함");
  });

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

  it("breaks a run-on special clause at sentence ends without changing the text", () => {
    const text = "임차인은 전입신고를 마친다. 임대인은 저당권을 설정할 수 없다. ( □ 동의 ☑ 미동의 ) 철거 계획이 있다.";

    const formatted = formatClauseText(text);

    expect(formatted.split("\n")).toEqual([
      "임차인은 전입신고를 마친다.",
      "임대인은 저당권을 설정할 수 없다.",
      "( □ 동의 ☑ 미동의 ) 철거 계획이 있다.",
    ]);
    expect(formatted.replace(/\n/g, " ")).toBe(text);
  });

  it("keeps cross references, amounts, and 가·나·다 list markers on the same line", () => {
    const crossReference = "제6조의3 제1항에 따라 30,000,000 원을 초과하는 경우 해제할 수 있다.";
    expect(formatClauseText(crossReference)).toBe(crossReference);

    // 목록 표시 "다."는 문장 끝이 아니므로 표시와 본문을 갈라 놓지 않는다.
    expect(formatClauseText("가. 첫째 내용 나. 둘째 내용 다. 셋째 내용")).toBe("가. 첫째 내용 나. 둘째 내용 다. 셋째 내용");
  });

  // 화면에서 문제가 된 실제 특약 원문. 문장 끝이 없는 서식 구간은 원문 그대로 이어 붙은 채 남는다.
  it("breaks the real special clause at sentence ends and leaves the form section intact", () => {
    const text = "주택을 인도받은 임차인은 2026년 9월 13일까지 주민등록(전입신고)과 주택임대차계약서상 확정일자를 받기로 하고, 임대인은 위 약정일자의 다음날 까지 임차주택에 저당권 등 담보권을 설정할 수 없다. 주택임대차계약과 관련하여 분쟁이 있는 경우 임대인 또는 임차인은 법원에 소를 제기하기 전에 먼저 주택임대차분쟁조정위원회에 조정을 신청한다. ( □ 동의 ☑ 미동의 ) 주택의 철거 또는 재건축에 관한 구체적 계획 ( □ 없음 ☑ 있음 ※공사시기: 2028년경 ※소요기간: 32개월 )";

    const lines = formatClauseText(text).split("\n");

    expect(lines).toHaveLength(3);
    expect(lines[0]).toMatch(/^주택을 인도받은 임차인은/);
    expect(lines[1]).toMatch(/^주택임대차계약과 관련하여/);
    expect(lines[2]).toMatch(/^\( □ 동의/);
    expect(lines.join(" ")).toBe(text);
  });

  it("splits joined clauses and ① sub-items without dropping content", () => {
    const text = "제9조(계약의 종료) 임차인은 반환한다., 제3조(수리) 합의한다. ① 임차인은 못한다. ② 임대인은 유지한다.";
    const lines = splitClauseText(text);
    expect(lines).toEqual([
      "제9조(계약의 종료) 임차인은 반환한다.",
      "제3조(수리) 합의한다.",
      "① 임차인은 못한다.",
      "② 임대인은 유지한다.",
    ]);
  });

  // 표 칸 구분은 공백 2칸 이상이 유일한 신호다. 1칸으로 뭉개면 라벨과 값이 붙어
  // "보증금  금 306,000,000 원정"이 "보증금금 306,000,000 원정"으로 읽힌다.
  it("keeps the table cell gap between a form label and its value", () => {
    const text = "제1조(보증금과 차임) 보 증 금  금 306,000,000 원정  계 약 금  금 30,600,000 원정";

    const [line] = splitClausesForDisplay(text);

    expect(line).toBe("제1조(보증금과 차임) 보 증 금  금 306,000,000 원정  계 약 금  금 30,600,000 원정");
    expect(cleanClauseLine("보 증 금     금 306,000,000 원정")).toBe("보 증 금  금 306,000,000 원정");
  });
});
