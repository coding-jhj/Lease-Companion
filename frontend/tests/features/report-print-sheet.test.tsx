// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ReportPrintSheet } from "../../src/features/result-report/ReportPrintSheet";
import type {
  DamagePatternComparisonDto,
  JudgmentGuidanceDto,
  JudgmentResultDto,
  StageGuidanceDto,
} from "../../src/types/api";

const result: JudgmentResultDto = {
  judgment_id: "J01",
  judgment_name: "임대인과 등기 소유자 일치",
  status: "불일치",
  urgency: "즉시 확인",
  triggers_actions: true,
  reason: "계약 상대방과 등기 소유자 이름이 다릅니다.",
  question: "임대인에게 등기 소유자와의 관계를 물어보세요.",
  recommended_actions: [],
  evidence_sources: [],
  limitations: "제출 자료를 기준으로 확인했습니다.",
};

const guidance: JudgmentGuidanceDto = {
  judgment_id: "J01",
  explanation: "계약 상대방이 등기 소유자인지 확인해야 합니다.",
  questions: [
    "임대인에게 등기 소유자와의 관계를 물어보세요.",
    "중개사에게 최신 등기를 확인한다.",
  ],
  request_templates: ["임대인에게 위임장을 요청한다."],
  signing_checklist: [],
  post_contract_actions: [],
  signing_checklist_items: [],
  post_contract_action_items: [],
  source_ids: [],
  generation_method: "template_fallback",
  provider_model: null,
  fallback_reason: null,
};

const guidanceOnly: JudgmentGuidanceDto = {
  ...guidance,
  judgment_id: "J99",
  questions: ["계약서의 주소를 다시 확인한다."],
  request_templates: [],
};

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
  before_deposit_questions: ["중개사에게 중개대상물 확인설명서를 요청한다."],
  signing_checklist: [],
  post_contract_actions: [],
  record_retention: ["계약서 사본을 보관하세요."],
  before_contract_actions: ["등기사항증명서를 확인하세요."],
  during_contract_actions: ["특약 문구를 확인하세요."],
  closing_day_actions: ["송금 전 계좌 명의를 확인하세요."],
  after_contract_actions: ["전입신고를 준비하세요."],
};

const pattern: DamagePatternComparisonDto = {
  pattern_id: "DP01",
  pattern_name: "소유자 불일치",
  status: "관련 확인 신호 있음",
  reason: "계약 상대방과 등기 소유자 이름을 비교해야 합니다.",
  related_rule_ids: [],
  related_judgment_ids: ["J01"],
  limitations: "제출 자료 기준입니다.",
  official_sources: [{
    source_id: "official-1",
    article_or_section: "제3조",
    title: "주택임대차보호법",
    institution: "국가법령정보센터",
    summary: "대항력 관련 공식 근거",
    source_url: null,
  }],
  reference_cases: [{
    reference_case_id: "case-1",
    title: "소유자 불일치 확인 사례",
    publisher: "공공기관 사례집",
    published_at: null,
    source_url: "https://example.com/case-1",
    summary: "계약 상대방 확인 사례",
    verification_scope: "비식별 공개 사례 제목 확인",
  }],
};

describe("ReportPrintSheet", () => {
  afterEach(cleanup);

  it("puts the action-first title, disclaimer, and sections in the same order as the result screen", () => {
    render(
      <ReportPrintSheet
        contractId={1}
        patterns={[pattern]}
        actionResults={[result]}
        results={[result]}
        guidance={[guidance, guidanceOnly]}
        specialClauseReviews={[]}
        specialClauseGuidance={[]}
        stageGuidance={stageGuidance}
      />,
    );

    expect(screen.getByRole("heading", { name: "내 계약 확인 결과", hidden: true })).toBeInTheDocument();
    const headings = screen.getAllByRole("heading", { hidden: true }).map((heading) => heading.textContent);
    expect(headings.indexOf("지금 먼저 확인할 일"))
      .toBeLessThan(headings.indexOf("물어볼 말"));
    expect(headings.indexOf("물어볼 말"))
      .toBeLessThan(headings.indexOf("계약 단계별 할 일"));
    expect(headings.indexOf("계약 단계별 할 일"))
      .toBeLessThan(headings.indexOf("판단 이유"));
    expect(headings.indexOf("판단 이유"))
      .toBeLessThan(headings.indexOf("문서 근거와 세부 판정 정보"));
    expect(headings.indexOf("문서 근거와 세부 판정 정보"))
      .toBeLessThan(headings.indexOf("비슷한 상황에서 확인할 점"));

    const questions = screen.getByRole("heading", { name: "물어볼 말", hidden: true }).closest("section")!;
    expect(within(questions).getByRole("heading", { name: "중개사에게 물어볼 말", hidden: true })).toBeInTheDocument();
    expect(within(questions).getByRole("heading", { name: "임대인에게 물어볼 말", hidden: true })).toBeInTheDocument();
    expect(within(questions).getByRole("heading", { name: "내가 문서에서 다시 볼 것", hidden: true })).toBeInTheDocument();
    for (const question of [
      "임대인에게 등기 소유자와의 관계를 물어보세요.",
      "중개사에게 최신 등기를 확인하세요.",
      "임대인에게 위임장을 요청하세요.",
      "중개사에게 중개대상물 확인설명서를 요청하세요.",
      "계약서의 주소를 다시 확인하세요.",
    ]) {
      expect(within(questions).getByText(question)).toBeInTheDocument();
    }

    const detail = screen.getByRole("heading", { name: "문서 근거와 세부 판정 정보", hidden: true }).closest("section")!;
    expect(within(detail).getByText(/J01 · 상태: 불일치 · 시급도: 즉시 확인/)).toBeInTheDocument();
    for (const title of ["지금 먼저 확인할 일", "물어볼 말", "계약 단계별 할 일", "판단 이유", "비슷한 상황에서 확인할 점"]) {
      const section = screen.getByRole("heading", { name: title, hidden: true }).closest("section")!;
      expect(section).not.toHaveTextContent("J01 · 상태: 불일치 · 시급도: 즉시 확인");
    }

    const references = screen.getByRole("heading", { name: "비슷한 상황에서 확인할 점", hidden: true }).closest("section")!;
    const official = within(references).getByRole("heading", { name: "공식 근거", hidden: true }).closest("section")!;
    const similar = within(references).getByRole("heading", { name: "유사 참고 사례", hidden: true }).closest("section")!;
    expect(official).toHaveTextContent("주택임대차보호법 제3조");
    expect(official).not.toHaveTextContent("소유자 불일치 확인 사례");
    expect(similar).toHaveTextContent("소유자 불일치 확인 사례");
    expect(similar).not.toHaveTextContent("주택임대차보호법 제3조");
    expect(screen.queryByText("임차인 방어 리포트")).not.toBeInTheDocument();
    expect(screen.getByText("이 문서는 계약의 안전·위법 여부를 판정하는 법률 의견서가 아닙니다. 서명·송금 전에 확인할 질문과 행동을 정리한 자료입니다.")).toBeInTheDocument();
  });

  it("does not print empty section titles when the matching data is absent", () => {
    render(
      <ReportPrintSheet
        contractId={1}
        patterns={[]}
        actionResults={[]}
        results={[]}
        guidance={[]}
        specialClauseReviews={[]}
        specialClauseGuidance={[]}
        stageGuidance={null}
      />,
    );

    for (const title of [
      "지금 먼저 확인할 일",
      "물어볼 말",
      "계약 단계별 할 일",
      "판단 이유",
      "문서 근거와 세부 판정 정보",
      "비슷한 상황에서 확인할 점",
    ]) {
      expect(screen.queryByRole("heading", { name: title, hidden: true })).not.toBeInTheDocument();
    }
  });

  it("uses legacy stage guidance when stage-specific actions are absent", () => {
    render(
      <ReportPrintSheet
        contractId={1}
        patterns={[]}
        actionResults={[]}
        results={[]}
        guidance={[]}
        specialClauseReviews={[]}
        specialClauseGuidance={[]}
        stageGuidance={{
          ...stageGuidance,
          signing_checklist: ["계약서 원본을 확인하세요."],
          post_contract_actions: ["전입신고를 하세요."],
          record_retention: [],
          before_contract_actions: undefined,
          during_contract_actions: undefined,
          closing_day_actions: undefined,
          after_contract_actions: undefined,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "계약 단계별 할 일", hidden: true })).toBeInTheDocument();
    expect(screen.getAllByText("계약서 원본을 확인하세요.")).toHaveLength(2);
    expect(screen.getByText("전입신고를 하세요.")).toBeInTheDocument();
  });
});
