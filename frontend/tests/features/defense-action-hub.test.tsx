// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DefenseActionHub } from "../../src/features/question-cards/DefenseActionHub";
import type { RuleResultDto, Urgency } from "../../src/types/api";

function ruleWithQuestion(rule_id: string, urgency: Urgency, question: string): RuleResultDto {
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
});
