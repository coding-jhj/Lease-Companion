// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen, within } from "@testing-library/react";
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
  triggers_actions: true,
});

describe("PriorityGroups", () => {
  it("maps urgency to the three accessible display groups", () => {
    render(<PriorityGroups items={[item("R01", "즉시 확인"), item("R02", "계약 전 확인"), item("R03", "참고", null)]} />);

    const mandatory = screen.getByRole("heading", { name: "반드시 확인" }).closest("section")!;
    expect(within(mandatory).getAllByRole("article")).toHaveLength(1);
    expect(mandatory.querySelector(".priority-group__items"))
      .toHaveClass("priority-group__items--three-column");
    for (const label of ["확인 권장", "일반 확인"]) {
      const button = screen.getByRole("button", { name: new RegExp(`^${label}`) });
      expect(button).toHaveAttribute("aria-expanded", "false");
      expect(within(button.closest("section")!).queryByRole("article")).not.toBeInTheDocument();
      fireEvent.click(button);
      expect(within(button.closest("section")!).getAllByRole("article")).toHaveLength(1);
      expect(button.closest("section")?.querySelector(".priority-group__items"))
        .toHaveClass("priority-group__items--three-column");
    }
    const generalCard = screen.getByRole("heading", { name: "R03 확인 항목" }).closest("article")!;
    fireEvent.click(within(generalCard).getByRole("button", { name: "자세히 보기" }));
    const dialog = screen.getByRole("dialog", { name: "R03 확인 항목" });
    expect(dialog).not.toHaveTextContent("사실 플래그");
    expect(dialog).not.toHaveTextContent("확인 한계");
    expect(within(dialog).getByText("금전 피해로 이어질 수 있어요")).toBeVisible();
    expect(within(dialog).getByText("무엇을 확인해야 하나요?")).toBeVisible();
    expect(within(dialog).getByText("등기사항증명서에 근저당권 등 담보가 잡혀 있는지 확인하는 항목입니다."))
      .toBeVisible();
    expect(within(dialog).getByText("선순위 담보가 있으면 집이 경매로 넘어갈 때 보증금을 온전히 돌려받지 못할 수 있습니다."))
      .toBeVisible();
  });

  it("uses the agreed urgency mapping", () => {
    expect(displayPriorityForUrgency("분석 불가")).toBe("반드시 확인");
    expect(displayPriorityForUrgency("계약 직후 조치")).toBe("확인 권장");
    expect(displayPriorityForUrgency("참고")).toBe("일반 확인");
  });

  it("keeps unavailable and external-data items in one collapsed group", () => {
    const { container } = render(<PriorityGroups items={[
      { ...item("R04", "분석 불가"), status: "확인 불가" },
      item("R20", "분석 불가"),
      item("R01", "즉시 확인"),
    ]} />);

    const currentView = within(container);
    const unavailableToggle = currentView.getByRole("button", { name: "지금 판단할 수 없는 항목 2개" });
    expect(unavailableToggle).toHaveAttribute("aria-expanded", "false");
    expect(currentView.queryByText("R20")).not.toBeInTheDocument();
    expect(currentView.getByRole("heading", { name: "R01 확인 항목" })).toBeInTheDocument();

    fireEvent.click(unavailableToggle);

    expect(currentView.getByRole("heading", { name: "R04 확인 항목" })).toBeInTheDocument();
    expect(currentView.getByRole("heading", { name: "R20 확인 항목" })).toBeInTheDocument();
    expect(container.querySelector(".unavailable-results .priority-group__items"))
      .toHaveClass("priority-group__items--three-column");
  });

  it("keeps the priority groups in the requested display order", () => {
    const { container } = render(<PriorityGroups items={[
      item("R01", "즉시 확인"),
      item("R02", "계약 전 확인"),
      item("R03", "참고"),
      { ...item("R04", "분석 불가"), status: "확인 불가" },
    ]} />);

    const mandatory = container.querySelector('[data-priority="반드시 확인"]')!;
    const recommended = container.querySelector('[data-priority="확인 권장"]')!;
    const general = container.querySelector('[data-priority="일반 확인"]')!;
    const unavailable = container.querySelector(".unavailable-results")!;

    expect(mandatory.compareDocumentPosition(recommended) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
    expect(recommended.compareDocumentPosition(general) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
    expect(general.compareDocumentPosition(unavailable) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
  });
});
