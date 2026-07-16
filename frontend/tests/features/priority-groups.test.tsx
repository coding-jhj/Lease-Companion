// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PriorityGroups, displayPriorityForUrgency } from "../../src/features/judgment-results/PriorityGroups";
import type { RuleResultDto, Urgency } from "../../src/types/api";

const item = (ruleId: string, urgency: Urgency, judgmentId: string | null = "J01"): RuleResultDto => ({
  rule_id: ruleId,
  rule_name: ruleId + " 확인 항목",
  judgment_id: judgmentId,
  status: "확인 필요",
  urgency,
  reason: "확인 설명",
  question: "확인 질문",
  recommended_actions: ["확인 행동"],
  limitations: "판정 한계",
  evidence_sources: [{
    source_id: "SRC-1",
    title: "공식 근거",
    institution: "공공기관",
    summary: null,
    source_url: null,
  }],
  completed: false,
});

describe("PriorityGroups", () => {
  it("maps urgency to the three accessible display groups", () => {
    render(<PriorityGroups items={[item("R01", "즉시 확인"), item("R02", "계약 전 확인"), item("R03", "참고", null)]} />);

    for (const label of ["반드시 확인", "확인 권장", "일반 확인"]) {
      const heading = screen.getByRole("heading", { name: label });
      expect(within(heading.closest("section")!).getAllByRole("article")).toHaveLength(1);
    }
    expect(screen.getByText("R03").closest("article")).toHaveTextContent("사실 플래그");
    expect(document.querySelectorAll(".evidence-list p")).toHaveLength(3);
  });

  it("uses the agreed urgency mapping", () => {
    expect(displayPriorityForUrgency("분석 불가")).toBe("반드시 확인");
    expect(displayPriorityForUrgency("계약 직후 조치")).toBe("확인 권장");
    expect(displayPriorityForUrgency("참고")).toBe("일반 확인");
  });
});
