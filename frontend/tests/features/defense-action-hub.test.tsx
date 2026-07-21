// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DefenseActionHub } from "../../src/features/question-cards/DefenseActionHub";
import type { RuleGuidanceDto, RuleResultDto, StageGuidanceDto, Urgency } from "../../src/types/api";

function ruleWithQuestion(
  rule_id: string,
  urgency: Urgency,
  question: string,
  triggers_actions = true,
): RuleResultDto {
  return {
    rule_id,
    rule_name: rule_id,
    judgment_id: null,
    status: "확인 필요",
    urgency,
    reason: "",
    question,
    recommended_actions: [],
    evidence_sources: [],
    limitations: "",
    completed: true,
    triggers_actions,
  };
}

function guidance(rule_id: string, questions: string[] = []): RuleGuidanceDto {
  return {
    rule_id,
    explanation: "",
    questions,
    signing_checklist: [],
    post_contract_actions: [],
    signing_checklist_items: [],
    post_contract_action_items: [],
    source_ids: [],
    generation_method: "template_fallback",
    provider_model: null,
    fallback_reason: null,
  };
}

afterEach(cleanup);

describe("DefenseActionHub", () => {
  it("shows the most urgent questions first, not the lowest rule numbers", () => {
    // 번호는 빠르지만 급하지 않은 질문 3개 + 번호는 늦지만 급한 질문 1개.
    // ID 순이면 긴급 질문이 상위 3개 밖으로 밀린다. 시급도 순이면 맨 위로 와야 한다.
    const results = [
      ruleWithQuestion("R01", "참고", "참고 질문 A"),
      ruleWithQuestion("R02", "참고", "참고 질문 B"),
      ruleWithQuestion("R03", "참고", "참고 질문 C"),
      ruleWithQuestion("R04", "즉시 확인", "긴급 질문"),
    ];

    render(<DefenseActionHub results={results} guidance={[]} stageGuidance={null} />);

    const questionGroup = screen.getByRole("heading", { name: "먼저 물어볼 질문" }).closest("section")!;
    const visible = within(questionGroup).getAllByRole("listitem");
    expect(visible).toHaveLength(3);
    expect(visible[0]).toHaveTextContent("긴급 질문");
    // 급하지 않은 R03 질문은 상위 3개에서 밀려 "더 보기"로 숨는다.
    expect(within(questionGroup).queryByText("참고 질문 C")).not.toBeInTheDocument();
  });

  it("shows only action-triggering results and prefers generated guidance for the same result", () => {
    const results = [
      ruleWithQuestion("R01", "즉시 확인", "규칙 원문 질문"),
      ruleWithQuestion("R02", "참고", "정상 판정 질문", false),
    ];

    render(<DefenseActionHub results={results} guidance={[guidance("R01", ["생성된 확인 질문"])]} stageGuidance={null} />);

    expect(screen.getByText("생성된 확인 질문")).toBeInTheDocument();
    expect(screen.queryByText("규칙 원문 질문")).not.toBeInTheDocument();
    expect(screen.queryByText("정상 판정 질문")).not.toBeInTheDocument();
  });

  it("merges duplicate post-contract reporting and move-in protection actions", () => {
    const stageGuidance: StageGuidanceDto = {
      contract_context: {
        contract_id: 1,
        contract_stage: "계약 직후",
        signed: true,
        deposit_paid: true,
        balance_payment_date: null,
        move_in_date: null,
      },
      before_deposit_questions: [],
      signing_checklist: [],
      post_contract_actions: [
        "계약 후 30일 이내에 임대차 신고를 한다.",
        "주민센터를 방문해 전입신고를 마친다.",
        "계약 후 30일 이내에 주택임대차 신고를 완료한다.",
        "전입신고와 확정일자를 확인한다.",
      ],
      record_retention: [],
    };

    render(<DefenseActionHub results={[]} guidance={[]} stageGuidance={stageGuidance} />);

    const postGroup = screen.getByRole("heading", { name: "계약 직후 행동" }).closest("section")!;
    expect(within(postGroup).getAllByRole("listitem")).toHaveLength(2);
    expect(within(postGroup).getByText(/계약 체결일부터 30일 이내/)).toBeInTheDocument();
    expect(within(postGroup).getByText(/실제 입주 후 전입신고·확정일자/)).toBeInTheDocument();
  });
});
