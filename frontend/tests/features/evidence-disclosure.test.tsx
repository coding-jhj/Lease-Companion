// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceDisclosure } from "../../src/features/evidence-sources/EvidenceDisclosure";

describe("EvidenceDisclosure", () => {
  it("separates source identity, long summary, original link, and limitations", () => {
    const longSummary = [
      "제11조(분쟁의 해결) 임대차 관련 분쟁은 협의하거나 조정을 신청할 수 있다.",
      "[특약사항]",
      "· 임차인은 약정일까지 전입신고와 확정일자를 받기로 한다.",
    ].join("\n");
    render(
      <EvidenceDisclosure
        idPrefix="R01"
        explanation="계약서 임대인과 등기 소유자가 같은지 확인하는 항목입니다."
        financialImpact="권한을 확인하지 않으면 보증금을 돌려받는 과정이 복잡해질 수 있습니다."
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
    expect(screen.getByRole("heading", { name: "[특약사항]" })).toBeInTheDocument();
    expect(screen.getByText("제11조(분쟁의 해결)")).toBeInTheDocument();
    expect(screen.getByText("임차인은 약정일까지 전입신고와 확정일자를 받기로 한다.")).toBeInTheDocument();
    expect(screen.getByText("[특약사항]").closest("details")).toHaveClass("evidence-summary");
    expect(screen.getByText("계약서 임대인과 등기 소유자가 같은지 확인하는 항목입니다.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /공식 원문 열기/ })).toHaveAttribute("target", "_blank");
    expect(screen.getByText("권한을 확인하지 않으면 보증금을 돌려받는 과정이 복잡해질 수 있습니다.")).toBeInTheDocument();
    expect(screen.getByText("이 결과만으로 법률적 결론을 내릴 수 없습니다.")).toBeInTheDocument();
  });

  it("shows a clear next step when no official source is connected", () => {
    render(
      <EvidenceDisclosure
        idPrefix="R02"
        explanation="계약 조건을 직접 확인하는 항목입니다."
        financialImpact="확인하지 않으면 예상하지 못한 비용이 생길 수 있습니다."
        limitations="추가 확인이 필요합니다."
        sources={[]}
      />,
    );

    expect(screen.getByLabelText("공식 근거 0건")).toBeInTheDocument();
    expect(screen.getByText("공식 근거가 없는 항목은 계약 상대방이나 관련 기관에 직접 확인해 주세요.")).toBeInTheDocument();
  });
});
