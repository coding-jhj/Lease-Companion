// @vitest-environment jsdom

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PriorityGroups, displayPriorityForUrgency } from "../../src/features/judgment-results/PriorityGroups";
import type { ReportItem } from "../../src/types/api";

const item = (judgmentId: string, urgency: string): ReportItem => ({
  judgmentId,
  title: `${judgmentId} 확인 항목`,
  status: "확인 필요",
  urgency,
  priority: "일반 확인",
  explanation: "확인 설명",
});

describe("PriorityGroups", () => {
  it("maps urgency to the three accessible display groups", () => {
    render(<PriorityGroups items={[item("J01", "즉시 확인"), item("J02", "계약 전 확인"), item("J03", "참고")]} />);

    for (const label of ["반드시 확인", "확인 권장", "일반 확인"]) {
      const heading = screen.getByRole("heading", { name: label });
      expect(within(heading.closest("section")!).getAllByRole("article")).toHaveLength(1);
    }
  });

  it("uses the agreed urgency mapping", () => {
    expect(displayPriorityForUrgency("분석 불가")).toBe("반드시 확인");
    expect(displayPriorityForUrgency("계약 직후 조치")).toBe("확인 권장");
    expect(displayPriorityForUrgency("참고")).toBe("일반 확인");
  });
});
