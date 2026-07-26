// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  buildQuestionGroups,
  QuestionHub,
  StageActions,
} from "../../src/features/question-cards/DefenseActionHub";
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

describe("QuestionHub", () => {
  it("builds every prioritized question source into target groups", () => {
    const urgentGuidance = {
      ...guidance("R01", [
        "중개사에게 등기 발급일을 확인한다.",
        "임대인에게 소유자 관계를 확인한다.",
      ]),
      request_templates: ["임대인에게 위임장을 요청한다."],
    };
    const guidanceOnly = guidance("R99", ["계약서의 주소를 다시 확인한다."]);
    const stageGuidance: StageGuidanceDto = {
      contract_context: {
        contract_id: 1,
        contract_stage: "서명 전",
        signed: false,
        deposit_paid: false,
        balance_payment_date: null,
        move_in_date: null,
      },
      before_deposit_questions: ["중개사에게 최신 등기를 요청한다."],
      signing_checklist: [],
      post_contract_actions: [],
      record_retention: [],
    };

    const groups = buildQuestionGroups(
      [
        ruleWithQuestion("R01", "즉시 확인", "같은 결과의 fallback 질문"),
        ruleWithQuestion("R02", "계약 전 확인", "임대인에게 계좌 명의를 확인한다."),
      ],
      [urgentGuidance, guidanceOnly],
      stageGuidance,
    );

    expect(groups["중개사"]).toEqual([
      "중개사에게 등기 발급일을 확인하세요.",
      "중개사에게 최신 등기를 요청하세요.",
    ]);
    expect(groups["임대인"]).toEqual([
      "임대인에게 소유자 관계를 확인하세요.",
      "임대인에게 위임장을 요청하세요.",
      "임대인에게 계좌 명의를 확인하세요.",
    ]);
    expect(groups["내가 다시 확인"]).toEqual(["계약서의 주소를 다시 확인하세요."]);
    expect(Object.values(groups).flat()).not.toContain("같은 결과의 fallback 질문입니다.");
  });

  it("shows the most urgent questions first, not the lowest rule numbers", () => {
    // 번호는 빠르지만 급하지 않은 질문 3개 + 번호는 늦지만 급한 질문 1개.
    // ID 순이면 긴급 질문이 상위 3개 밖으로 밀린다. 시급도 순이면 맨 위로 와야 한다.
    const results = [
      ruleWithQuestion("R01", "참고", "참고 질문 A"),
      ruleWithQuestion("R02", "참고", "참고 질문 B"),
      ruleWithQuestion("R03", "참고", "참고 질문 C"),
      ruleWithQuestion("R04", "즉시 확인", "긴급 질문"),
    ];

    render(<QuestionHub results={results} guidance={[]} stageGuidance={null} />);

    const questionGroup = screen.getByRole("heading", { name: "문서에서 다시 확인할 내용"}).closest("section")!;
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

    render(<QuestionHub results={results} guidance={[guidance("R01", ["생성된 확인 질문"])]} stageGuidance={null} />);

    expect(screen.getByText("생성된 확인 질문")).toBeInTheDocument();
    expect(screen.queryByText("규칙 원문 질문")).not.toBeInTheDocument();
    expect(screen.queryByText("정상 판정 질문")).not.toBeInTheDocument();
  });

  it("groups deduplicated questions by broker, landlord, and self-check target", () => {
    const results = [
      ruleWithQuestion("R01", "즉시 확인", "중개사에게 최신 등기 발급일을 물어보세요."),
      ruleWithQuestion("R02", "즉시 확인", "임대인에게 입금 계좌 명의를 물어보세요."),
      ruleWithQuestion("R03", "계약 전 확인", "계약서의 금액 표기를 다시 확인하세요."),
    ];
    const stageGuidance: StageGuidanceDto = {
      contract_context: {
        schema_version: "1.9.0",
        contract_id: 1,
        contract_type: "전세",
        contract_stage: "서명 전",
        signed: false,
        deposit_paid: false,
        balance_payment_date: null,
        move_in_date: null,
        is_proxy_contract: false,
      },
      before_deposit_questions: ["중개사에게 최신 등기 발급일을 물어보세요."],
      signing_checklist: [],
      post_contract_actions: [],
      record_retention: [],
    };

    render(<QuestionHub results={results} guidance={[]} stageGuidance={stageGuidance} />);

    const broker = screen.getByRole("heading", { name: "중개사에게 확인해야 할 사항" }).closest("section")!;
    const landlord = screen.getByRole("heading", { name: "임대인에게 확인해야 할 사항" }).closest("section")!;
    const self = screen.getByRole("heading", { name: "문서에서 다시 확인할 내용"}).closest("section")!;
    expect(within(broker).getAllByRole("listitem")).toHaveLength(1);
    expect(within(landlord).getAllByRole("listitem")).toHaveLength(1);
    expect(within(self).getAllByRole("listitem")).toHaveLength(1);
    expect(self).toHaveClass("action-hub__group--wide");
  });

  it("normalizes polite endings before deduplicating rendered questions", () => {
    const results = [
      ruleWithQuestion("R01", "즉시 확인", "계좌 명의를 확인한다."),
      ruleWithQuestion("R02", "계약 전 확인", "계좌 명의를 확인하세요."),
    ];

    render(<QuestionHub results={results} guidance={[]} stageGuidance={null} />);

    const landlord = screen.getByRole("heading", { name: "임대인에게 확인해야 할 사항" }).closest("section")!;
    expect(within(landlord).getAllByRole("listitem")).toHaveLength(1);
    expect(within(landlord).getByText("계좌 명의를 확인하세요.")).toBeInTheDocument();
  });

  it("places one visible person card beside the document card", () => {
    render(
      <QuestionHub
        results={[
          ruleWithQuestion("R01", "즉시 확인", "임대인에게 입금 계좌 명의를 확인하세요."),
          ruleWithQuestion("R02", "계약 전 확인", "계약서의 금액 표기를 다시 확인하세요."),
        ]}
        guidance={[]}
        stageGuidance={null}
      />,
    );

    expect(screen.queryByRole("heading", { name: "중개사에게 확인해야 할 사항" })).not.toBeInTheDocument();
    const landlordSection = screen.getByRole("heading", { name: "임대인에게 확인해야 할 사항" }).closest("section")!;
    const documentSection = screen.getByRole("heading", { name: "문서에서 다시 확인할 내용" }).closest("section")!;
    expect(landlordSection).not.toHaveClass("action-hub__group--wide");
    expect(documentSection).not.toHaveClass("action-hub__group--wide");
  });

  it("uses the full row when only the document card is visible", () => {
    render(
      <QuestionHub
        results={[ruleWithQuestion("R01", "즉시 확인", "계약서의 금액 표기를 다시 확인하세요.")]}
        guidance={[]}
        stageGuidance={null}
      />,
    );

    expect(screen.queryByRole("heading", { name: "중개사에게 확인해야 할 사항" })).not.toBeInTheDocument();
    const documentSection = screen.getByRole("heading", { name: "문서에서 다시 확인할 내용" }).closest("section")!;
    expect(documentSection).toHaveClass("action-hub__group--wide");
  });

  it("shows questions as plain text without copy buttons", () => {
    const question = "임대인에게 입금 계좌 명의를 물어보세요.";

    render(<QuestionHub results={[ruleWithQuestion("R01", "즉시 확인", question)]} guidance={[]} stageGuidance={null} />);

    const landlord = screen.getByRole("heading", { name: "임대인에게 확인해야 할 사항" }).closest("section")!;
    expect(within(landlord).getByText(question)).toBeInTheDocument();
    expect(within(landlord).queryByRole("button", { name: /복사/ })).not.toBeInTheDocument();
  });

});

describe("StageActions", () => {
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

    render(<StageActions results={[]} guidance={[]} stageGuidance={stageGuidance} />);

    // 5개 블록이 모두 같은 펼침·접기 버튼을 갖고, 처음에는 전부 접혀 있다.
    for (const title of ["계약 전", "계약 중", "잔금·입주 당일", "계약 후", "보관할 자료"]) {
      expect(screen.getByRole("button", { name: new RegExp(`^${title}`) }))
        .toHaveAttribute("aria-expanded", "false");
    }
    expect(screen.queryByText("지금 단계를 먼저 펼쳐 두었습니다. 다른 단계는 눌러서 확인하세요.")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^계약 후/ }));
    const postGroup = screen.getByRole("heading", { name: "계약 후" }).closest("section")!;
    expect(within(postGroup).getAllByRole("listitem")).toHaveLength(2);
    expect(within(postGroup).getByText(/계약 체결일부터 30일 이내/)).toBeInTheDocument();
    expect(within(postGroup).getByText(/실제 입주 후 전입신고·확정일자/)).toBeInTheDocument();
  });
});
