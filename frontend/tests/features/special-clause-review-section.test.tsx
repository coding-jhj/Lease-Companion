// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SpecialClauseReviewSection } from "../../src/features/special-clauses/SpecialClauseReviewSection";
import type { SpecialClauseGuidanceDto, SpecialClauseReviewDto } from "../../src/types/api";

const review: SpecialClauseReviewDto = {
  clause_id: "CLAUSE-001",
  original_text: "보증금은 신규 임차인이 입주한 후 반환한다.",
  catalog_ids: ["SC-DEFERRED-REFUND"],
  match_method: "catalog_pattern",
  related_rule_ids: ["R08"],
  related_judgment_ids: ["J10"],
  status: "확인 필요",
  urgency: "즉시 확인",
  reason: "보증금 반환이 신규 임차인 입주라는 미래 사건에 연결되어 있습니다.",
  triggers_actions: true,
  evidence_sources: [{
    source_id: "SRC-HOUSING-LEASE-ACT",
    article_or_section: "제4조 제2항",
    title: "주택임대차보호법",
    institution: "국가법령정보센터",
    summary: "임대차가 끝난 경우에도 임차인이 보증금을 반환받을 때까지 임대차관계는 존속합니다.",
    source_url: "https://law.go.kr/example",
  }],
  limitations: "계약 전체 문맥과 실제 반환 상황은 별도 확인이 필요합니다.",
};

const guidance: SpecialClauseGuidanceDto = {
  clause_id: "CLAUSE-001",
  plain_explanation: "새 임차인이 들어오지 않으면 반환 시점이 늦어질 수 있는 문구입니다.",
  confirmation_questions: ["새 임차인 입주와 관계없이 반환받을 수 있나요?"],
  revision_requests: ["계약 종료 시 반환하도록 문구를 수정해 주세요."],
  source_ids: ["SRC-HOUSING-LEASE-ACT"],
  generation_method: "template_fallback",
};

afterEach(cleanup);

describe("SpecialClauseReviewSection", () => {
  it("shows original text, priority, explanation, evidence, questions, and revision requests", () => {
    render(<SpecialClauseReviewSection reviews={[review]} guidance={[guidance]} generationFailed={false} />);

    const section = screen.getByRole("heading", { name: "확인이 필요한 특약" }).closest("section")!;
    expect(within(section).getByText(review.original_text)).toBeInTheDocument();
    expect(within(section).getByText("반드시 확인")).toBeInTheDocument();
    expect(within(section).getByText(guidance.plain_explanation)).toBeInTheDocument();
    expect(within(section).getByText("제4조 제2항")).toBeInTheDocument();
    expect(within(section).getByRole("link", { name: /공식 원문 열기/ })).toHaveAttribute("href", "https://law.go.kr/example");
    expect(within(section).getByText(guidance.confirmation_questions[0])).toBeInTheDocument();
    expect(within(section).getByText(guidance.revision_requests[0])).toBeInTheDocument();
  });

  it("keeps Python review visible when evidence and generation are unavailable", () => {
    render(<SpecialClauseReviewSection reviews={[{ ...review, evidence_sources: [] }]} guidance={[]} generationFailed />);

    expect(screen.getByRole("status")).toHaveTextContent("특약 원문과 Python 판정은 그대로 표시");
    expect(screen.getByText(review.original_text)).toBeInTheDocument();
    expect(screen.getByText("현재 연결된 공식자료가 없습니다.")).toBeInTheDocument();
    expect(screen.getByText(/안내 생성에 실패했습니다/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "수정 요청 문구" })).not.toBeInTheDocument();
  });

  it("hides the section when no clause review exists", () => {
    const { container } = render(<SpecialClauseReviewSection reviews={[]} guidance={[]} generationFailed={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
