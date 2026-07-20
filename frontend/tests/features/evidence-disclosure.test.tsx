// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceDisclosure } from "../../src/features/evidence-sources/EvidenceDisclosure";

describe("EvidenceDisclosure", () => {
  it("separates source identity, long summary, original link, and limitations", () => {
    const longSummary = "임대차계약에서 확인할 내용을 설명하는 긴 공식 근거 요약입니다.";
    render(
      <EvidenceDisclosure
        idPrefix="R01"
        limitations="이 결과만으로 법률적 결론을 내릴 수 없습니다."
        sources={[{
          source_id: "SRC-1",
          title: "주택임대차 표준계약서",
          institution: "법무부",
          summary: longSummary,
          source_url: "https://example.com/source",
        }]}
      />,
    );

    expect(screen.getByLabelText("공식 근거 1건")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "주택임대차 표준계약서" })).toBeInTheDocument();
    expect(screen.getByText("법무부")).toBeInTheDocument();
    expect(screen.getByText(longSummary).closest("details")).toHaveClass("evidence-summary");
    expect(screen.getByRole("link", { name: /공식 원문 열기/ })).toHaveAttribute("target", "_blank");
    expect(screen.getByText("이 결과만으로 법률적 결론을 내릴 수 없습니다.")).toBeInTheDocument();
  });

  it("shows a clear next step when no official source is connected", () => {
    render(
      <EvidenceDisclosure
        idPrefix="R02"
        limitations="추가 확인이 필요합니다."
        sources={[]}
      />,
    );

    expect(screen.getByLabelText("공식 근거 0건")).toBeInTheDocument();
    expect(screen.getByText("공식 근거가 없는 항목은 계약 상대방이나 관련 기관에 직접 확인해 주세요.")).toBeInTheDocument();
  });
});
