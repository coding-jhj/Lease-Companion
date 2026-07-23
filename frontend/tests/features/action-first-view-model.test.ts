import { describe, expect, it } from "vitest";
import {
  buildActionFirstItems,
  type ActionFirstItem,
} from "../../src/features/result-report/actionFirstViewModel";
import type {
  JudgmentGuidanceDto,
  JudgmentResultDto,
  RuleGuidanceDto,
  RuleResultDto,
  StageGuidanceDto,
  Urgency,
} from "../../src/types/api";

function rule(
  ruleId: string,
  urgency: Urgency,
  overrides: Partial<RuleResultDto> = {},
): RuleResultDto {
  return {
    rule_id: ruleId,
    rule_name: `${ruleId} 확인 항목`,
    judgment_id: null,
    status: "확인 필요",
    urgency,
    reason: `${ruleId} 문서 내용을 다시 확인하세요.`,
    question: `${ruleId} 확인 질문`,
    recommended_actions: [],
    evidence_sources: [],
    limitations: "",
    completed: true,
    triggers_actions: true,
    ...overrides,
  };
}

function judgment(
  judgmentId: `J${string}`,
  urgency: Urgency,
  overrides: Partial<JudgmentResultDto> = {},
): JudgmentResultDto {
  return {
    judgment_id: judgmentId,
    judgment_name: `${judgmentId} 확인 항목`,
    status: "확인 필요",
    urgency,
    reason: `${judgmentId} 문서 내용을 다시 확인하세요.`,
    question: `${judgmentId} 확인 질문`,
    recommended_actions: [],
    evidence_sources: [],
    limitations: "",
    triggers_actions: true,
    ...overrides,
  };
}

function ruleGuidance(ruleId: string, question: string): RuleGuidanceDto {
  return {
    rule_id: ruleId,
    explanation: `${ruleId}을 확인해야 하는 이유입니다.`,
    questions: [question],
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

function judgmentGuidance(judgmentId: string, question: string): JudgmentGuidanceDto {
  return {
    judgment_id: judgmentId,
    explanation: `${judgmentId}을 확인해야 하는 이유입니다.`,
    questions: [question],
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

describe("buildActionFirstItems", () => {
  it("sorts actions by display priority and attaches timing, target, and generated question", () => {
    const results = [
      rule("R03", "참고"),
      judgment("J02", "계약 전 확인"),
      rule("R01", "즉시 확인"),
    ];
    const guidance = [
      ruleGuidance("R01", "임대인에게 계약 권한 서류를 보여 달라고 물어보세요."),
      judgmentGuidance("J02", "중개사에게 주소가 같은지 확인해 달라고 물어보세요."),
    ];

    const items: ActionFirstItem[] = buildActionFirstItems(results, guidance);

    expect(items.map((item) => item.priority)).toEqual([
      "반드시 확인",
      "확인 권장",
      "일반 확인",
    ]);
    expect(items[0]).toMatchObject({
      timing: "서명·송금 전에 확인",
      questionTarget: "임대인",
      question: "임대인에게 계약 권한 서류를 보여 달라고 물어보세요.",
    });
  });

  it("excludes cannot-judge items from top actions without mutating source results", () => {
    const unavailable = rule("R20", "분석 불가", { status: "확인 불가" });
    const visible = judgment("J01", "즉시 확인", { status: "불일치" });
    const originalVisible = structuredClone(visible);

    const items = buildActionFirstItems([unavailable, visible], []);

    expect(items).toHaveLength(1);
    expect(items[0].sourceResult).toBe(visible);
    expect(visible).toEqual(originalVisible);
  });

  it("uses only neutral result copy and no question when matching guidance is absent", () => {
    const source = judgment("J08", "계약 전 확인", {
      judgment_name: "지급일·입주일·계약기간 확인",
      reason: "기재된 날짜를 문서에서 다시 대조해 주세요.",
      question: "결과 원문의 질문",
    });

    const [item] = buildActionFirstItems([source], []);

    expect(item).toMatchObject({
      title: "지급일·입주일·계약기간 확인",
      reason: "기재된 날짜를 문서에서 다시 대조해 주세요.",
      questionTarget: "내가 다시 확인",
      question: null,
    });
    expect(JSON.stringify(item)).not.toMatch(/안전|위험|사기|추천|거절/);
  });

  it("uses a current-stage timing after the contract is signed", () => {
    const stageGuidance: StageGuidanceDto = {
      contract_context: {
        schema_version: "1.9.0",
        contract_id: 1,
        contract_type: "전세",
        contract_stage: "계약 직후",
        signed: true,
        deposit_paid: true,
        balance_payment_date: null,
        move_in_date: null,
        is_proxy_contract: false,
      },
      before_deposit_questions: [],
      signing_checklist: [],
      post_contract_actions: [],
      record_retention: [],
    };

    const items = buildActionFirstItems([
      rule("R01", "즉시 확인"),
      judgment("J08", "계약 전 확인"),
    ], [], stageGuidance);

    expect(items.map((item) => item.timing)).toEqual([
      "계약 후 지금 확인",
      "계약 후 지금 확인",
    ]);
    expect(items.map((item) => item.sourceResult.urgency)).toEqual([
      "즉시 확인",
      "계약 전 확인",
    ]);
  });
});
