// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import analysisRunResultFixture from "../../../data/sample/fixtures/case-001/analysis_run_result.json";
import generationResultFixture from "../../../data/sample/fixtures/case-001/generation_result.json";
import { ResultReportPage } from "../../src/pages/result-report/ResultReportPage";
import { mvpService } from "../../src/services/mvpService";
import type {
  AnalysisRunDetailDto,
  AnalysisRunResultDto,
  GenerationResultDto,
  SpecialClauseGuidanceDto,
  SpecialClauseReviewDto,
} from "../../src/types/api";

// 판정 축이 늘어날 때마다 고치지 않도록 fixture에서 파생한다.
const fixtureJudgmentIds = (analysisRunResultFixture as AnalysisRunResultDto).judgments.map(
  (item) => item.judgment_id,
);

const specialClauseReview: SpecialClauseReviewDto = {
  clause_id: "CLAUSE-001",
  original_text: "보증금은 신규 임차인이 입주한 후 반환한다.",
  catalog_ids: ["SC-DEFERRED-REFUND"],
  match_method: "catalog_pattern",
  related_rule_ids: ["R08"],
  related_judgment_ids: ["J10"],
  status: "확인 필요",
  urgency: "즉시 확인",
  reason: "반환 조건이 신규 임차인 입주에 연결되어 있습니다.",
  triggers_actions: true,
  evidence_sources: [],
  limitations: "공식 근거를 확인하지 못했습니다.",
};

const specialClauseGuidance: SpecialClauseGuidanceDto = {
  clause_id: "CLAUSE-001",
  plain_explanation: "신규 임차인이 없으면 반환이 늦어질 수 있습니다.",
  confirmation_questions: ["신규 임차인과 관계없이 반환하나요?"],
  revision_requests: ["계약 종료 시 반환하도록 수정해 주세요."],
  source_ids: [],
  generation_method: "template_fallback",
};

function detail(generationStatus: AnalysisRunDetailDto["generation_status"] = "completed"): AnalysisRunDetailDto {
  return {
    analysis_run_id: "RUN-1001-001",
    input_snapshot_id: "SNAP-1001",
    status: "completed",
    error: null,
    created_at: "2026-07-16T00:00:00Z",
    result: {
      ...(analysisRunResultFixture as AnalysisRunResultDto),
    },
    generation_result: generationStatus === "completed"
      ? generationResultFixture as GenerationResultDto
      : null,
    generation_status: generationStatus,
    generation_error: generationStatus === "failed" ? "안내 생성에 실패했습니다. 규칙 판정 결과는 정상입니다." : null,
  };
}

function fallbackDetail(): AnalysisRunDetailDto {
  const run = detail();
  const result = run.result as AnalysisRunResultDto;
  return {
    ...run,
    result: {
      ...result,
      judgments: result.judgments.map((item) =>
        ["J10", "J11", "J12"].includes(item.judgment_id)
          ? {
              ...item,
              status: "확인 필요" as const,
              reason: `${item.judgment_name}에 필요한 분류 후보를 확정할 수 없어 추가 확인이 필요합니다.`,
            }
          : item,
      ),
    },
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/contracts/1001/report?analysisRunId=RUN-1001-001"]}>
      <Routes>
        <Route path="/contracts/:contractId/report" element={<ResultReportPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function expandAllResultGroups() {
  for (const label of ["확인 권장", "일반 확인"]) {
    fireEvent.click(screen.getByRole("button", { name: new RegExp(`^${label}`) }));
  }
  const unavailableToggle = screen.queryByRole("button", { name: /^지금 판단할 수 없는 항목/ });
  if (unavailableToggle) fireEvent.click(unavailableToggle);
}

beforeEach(() => {
  vi.spyOn(mvpService, "getFeedback").mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ResultReportPage", () => {
  it("shows one merged result list per tab without repeating the same item", async () => {
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(detail());

    renderPage();

    expect(screen.getByText("확인 결과를 불러오는 중")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "계약서 임대인=등기 소유자" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /계약금을 보내기 전에 \d+가지를 먼저 확인해 주세요/ })).toBeInTheDocument();
    // 같은 판정을 "먼저 할 일"과 "왜 확인해야 하나요?"로 두 번 보여주지 않는다.
    expect(screen.queryByRole("heading", { name: "먼저 할 일" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "왜 확인해야 하나요?" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "계약서 임대인=등기 소유자" })).toHaveLength(1);
    expect(screen.getByLabelText("확인 우선순위 전체 개수")).toBeInTheDocument();
    // 상단 요약 개수는 하단 그룹 개수와 같아야 한다("지금 판단할 수 없는 항목"은 양쪽 모두 제외).
    for (const priority of ["반드시 확인", "확인 권장", "일반 확인"]) {
      const top = document.querySelector(`[aria-label="확인 우선순위 전체 개수"] [data-priority="${priority}"] strong`);
      const bottom = document.querySelector(`.priority-group[data-priority="${priority}"] .priority-count`);
      expect(top?.textContent).toBe(`${bottom?.textContent}개`);
    }

    // 병합된 카드가 시점·상태·물어볼 말을 함께 보여준다.
    const firstCard = document.querySelector("#first-action-item")!;
    expect(firstCard).toHaveTextContent("서명·송금 전에 확인");
    expect(firstCard).toHaveTextContent("불일치");
    expect(firstCard).toHaveTextContent("임대인");
    // 생성 문구의 제목 반복과 공통 꼬리말은 카드 본문에서 덜어낸다.
    expect(firstCard.querySelector("p")?.textContent).not.toMatch(/^계약서 임대인=등기 소유자:/);
    expect(firstCard.querySelector("p")?.textContent).not.toMatch(/공식 근거와 함께 확인해 주세요\.$/);

    expect(screen.getByRole("button", { name: /^확인 권장/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: /^일반 확인/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: /^지금 판단할 수 없는 항목/ })).toHaveAttribute("aria-expanded", "false");
    expandAllResultGroups();
    expect(document.querySelectorAll(".result-card")).toHaveLength(fixtureJudgmentIds.length);
    for (const judgmentId of fixtureJudgmentIds) {
      expect(screen.getByText(judgmentId)).toBeInTheDocument();
    }

    // 확인 항목 탭에서는 질문 목록·단계별 행동을 함께 쌓아 보여주지 않는다(다른 패널은 hidden).
    expect(screen.queryByRole("heading", { name: "상대방에게 물어볼 말" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "계약 단계별 행동" })).not.toBeInTheDocument();
    expect(document.querySelector("#report-panel-questions")).toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("tab", { name: "물어볼 말" }));
    expect(screen.getByRole("heading", { name: "상대방에게 물어볼 말" })).toBeInTheDocument();
    for (const title of ["중개사에게 물어볼 말", "임대인에게 물어볼 말", "내가 문서에서 다시 볼 것"]) {
      expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    }
    const question = "등기상 소유자와 계약자가 다른 이유와 계약 권한을 확인할 수 있는 서류를 보여주실 수 있나요?";
    expect(screen.getByRole("button", { name: `질문 복사: ${question}` })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "단계별 행동" }));
    for (const title of ["계약 전", "계약 중", "잔금·입주 당일", "계약 후", "보관할 자료"]) {
      expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    }
    // 지금 단계(계약금 입금 전)만 펼쳐 두고 나머지는 제목 줄만 보인다.
    expect(screen.getByRole("button", { name: /^잔금·입주 당일/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: /^보관할 자료/ })).toHaveAttribute("aria-expanded", "false");

    expect(screen.getByRole("heading", { name: "비슷한 상황에서 확인할 점" })).toBeInTheDocument();
    const firstPatternDetails = document.querySelector(".damage-patterns details") as HTMLDetailsElement;
    fireEvent.click(within(firstPatternDetails).getByText("근거와 분석 한계"));
    const referenceCases = within(firstPatternDetails).getByRole("region", { name: /검증된 유사 참고 사례$/ });
    expect(within(referenceCases).getByRole("heading", { name: "검증된 유사 참고 사례" })).toBeInTheDocument();
    expect(within(referenceCases).getByRole("link")).toHaveAttribute("href", expect.stringMatching(/^https:\/\//));
    expect(screen.getByRole("button", { name: "확인 결과 PDF 저장" })).toBeInTheDocument();
    // 전체 비교표는 접힌 상태로 시작한다(자료 부족 행이 화면을 차지하지 않게).
    expect((document.querySelector(".damage-table-fold") as HTMLDetailsElement).open).toBe(false);
    expect((document.querySelector(".feedback-fold") as HTMLDetailsElement).open).toBe(false);

    const hero = document.querySelector(".report-hero")!;
    const tabs = document.querySelector(".report-tabs")!;
    const panel = document.querySelector(".report-panel")!;
    const damageReference = document.querySelector(".damage-reference-section")!;
    const feedback = document.querySelector(".feedback-fold")!;
    expect(hero.compareDocumentPosition(tabs) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(tabs.compareDocumentPosition(panel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(panel.compareDocumentPosition(damageReference) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(damageReference.compareDocumentPosition(feedback) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    expect(screen.queryByText("R01")).not.toBeInTheDocument();

    // 탭을 돌아와도 펼쳐 둔 그룹이 그대로 남는다(패널을 지우지 않고 감추기만 하므로).
    fireEvent.click(screen.getByRole("tab", { name: "확인 항목" }));
    expect(screen.getByRole("button", { name: /^확인 권장/ })).toHaveAttribute("aria-expanded", "true");
    const j01 = screen.getByText("J01").closest("article");
    expect(j01).toHaveTextContent("상태: 불일치");
    expect(j01).toHaveTextContent("시급도: 즉시 확인");

    const j10 = screen.getByText("J10").closest("article");
    expect(j10).toHaveTextContent("상태: 명확");
    expect(j10).toHaveTextContent("보증금 반환 시점·조건 명확성");
    expect(document.body).not.toHaveTextContent("신규 임차인 입주와 관계없이");
    expect(screen.queryByRole("heading", { name: "확인이 필요한 특약" })).not.toBeInTheDocument();
  }, 10_000);

  it("shows special clause cards and includes them in the printable report", async () => {
    const run = detail();
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue({
      ...run,
      result: run.result ? { ...run.result, special_clause_reviews: [specialClauseReview] } : null,
      generation_result: run.generation_result
        ? { ...run.generation_result, special_clause_items: [specialClauseGuidance] }
        : null,
    });

    renderPage();

    const section = (await screen.findByRole("heading", { name: "확인이 필요한 특약" })).closest("section")!;
    expect(within(section).getByText(specialClauseReview.original_text)).toBeInTheDocument();
    expect(within(section).getByText(specialClauseGuidance.confirmation_questions[0])).toBeInTheDocument();
    expect(within(section).getByText(specialClauseGuidance.revision_requests[0])).toBeInTheDocument();
    const printSheet = document.querySelector(".report-print-sheet");
    // PDF 제목은 화면 제목과 같은 "내 계약 확인 결과"여야 한다. (print sheet는 aria-hidden)
    expect(printSheet?.querySelector("h1")).toHaveTextContent("내 계약 확인 결과");
    expect(printSheet).toHaveTextContent("확인이 필요한 특약");
    expect(printSheet).toHaveTextContent(specialClauseReview.original_text);
    expect(printSheet).toHaveTextContent(specialClauseGuidance.confirmation_questions[0]);
  });

  it("keeps the report available with user-safe J10-J12 statuses after classification fallback", async () => {
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(fallbackDetail());

    renderPage();

    expect(await screen.findByRole("tab", { name: "확인 항목" })).toBeInTheDocument();
    expandAllResultGroups();
    for (const judgmentId of ["J10", "J11", "J12"]) {
      const card = screen.getByText(judgmentId).closest("article");
      expect(card).toHaveTextContent("상태: 확인 필요");
    }
    fireEvent.click(screen.getByRole("tab", { name: "물어볼 말" }));
    expect(screen.getByRole("heading", { name: "상대방에게 물어볼 말" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("provider_unavailable");
    expect(document.body).not.toHaveTextContent("classification provider");
  });

  it("keeps rule results visible and shows a banner when only generation failed", async () => {
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(detail("failed"));

    renderPage();

    expect(await screen.findByText("확인 결과는 준비됐지만 쉬운 설명을 만들지 못했습니다. 확인 항목과 문서 근거는 그대로 볼 수 있습니다.")).toBeInTheDocument();
    expandAllResultGroups();
    expect(document.querySelectorAll(".result-card")).toHaveLength(fixtureJudgmentIds.length);
    expect(screen.getByText("J01")).toBeInTheDocument();
    expect(screen.queryByText("R01")).not.toBeInTheDocument();
  });

  it("shows an empty report state when a completed response has no rule results", async () => {
    const empty = detail();
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue({
      ...empty,
      result: empty.result ? { ...empty.result, results: [], judgments: [] } : null,
      generation_result: null,
    });

    renderPage();

    expect(await screen.findByText("아직 준비된 확인 결과가 없습니다")).toBeInTheDocument();
  });

  it("uses neutral copy for legacy rule-only reports and keeps the final action button", async () => {
    const run = detail();
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue({
      ...run,
      result: run.result ? { ...run.result, judgments: [] } : null,
    });

    renderPage();

    expect(await screen.findByRole("tab", { name: "확인 항목" })).toBeInTheDocument();
    expect(screen.queryByText("이전 분석의 핵심 규칙 결과")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "이제 할 일 확인하기" })).toBeInTheDocument();
  });

  it("keeps raw result-loading errors out of the user-facing retry guidance", async () => {
    vi.spyOn(mvpService, "getAnalysisDetail").mockRejectedValue(new Error("provider unavailable for case_id=CASE-001"));

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("확인 결과를 불러오지 못했습니다. 저장된 계약 정보는 변경되지 않았습니다. 다시 시도해 주세요.");
    expect(screen.getByRole("alert")).not.toHaveTextContent("provider unavailable");
    expect(screen.getByRole("alert")).not.toHaveTextContent("case_id");
  });
});
