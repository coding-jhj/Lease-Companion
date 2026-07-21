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
} from "../../src/types/api";

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
  it("renders one prioritized result list and one deduplicated defense action hub", async () => {
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(detail());

    renderPage();

    expect(screen.getByText("리포트를 불러오는 중")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "계약서 임대인=등기 소유자" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "서두르지 않아도 괜찮아요." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "가장 먼저 확인할 항목으로 이동" })).toHaveAttribute("href", "#first-priority-group");
    expect(screen.getByRole("heading", { name: "12가지 계약 확인 결과" })).toBeInTheDocument();
    expect(screen.getByText("내부 검사 결과의 중복을 빼고 계약에서 확인할 항목만 정리했습니다")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "방어 행동 허브" })).toBeInTheDocument();
    expect(screen.getByLabelText("확인 우선순위 전체 개수")).toBeInTheDocument();
    // 상단 요약 개수는 하단 그룹 개수와 같아야 한다("지금 판단할 수 없는 항목"은 양쪽 모두 제외).
    for (const priority of ["반드시 확인", "확인 권장", "일반 확인"]) {
      const top = document.querySelector(`[aria-label="확인 우선순위 전체 개수"] [data-priority="${priority}"] strong`);
      const bottom = document.querySelector(`.priority-group[data-priority="${priority}"] .priority-count`);
      expect(top?.textContent).toBe(`${bottom?.textContent}개`);
    }
    expect(document.querySelectorAll(".result-card").length).toBeLessThan(36);
    expect(screen.getByRole("button", { name: /^확인 권장/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: /^일반 확인/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: /^지금 판단할 수 없는 항목/ })).toHaveAttribute("aria-expanded", "false");
    expandAllResultGroups();
    expect(document.querySelectorAll(".result-card")).toHaveLength(12);
    for (const judgmentId of Array.from({ length: 12 }, (_, index) => `J${String(index + 1).padStart(2, "0")}`)) {
      expect(screen.getByText(judgmentId)).toBeInTheDocument();
    }
    for (const title of ["먼저 물어볼 질문", "수정·추가 요청 문구", "계약 전", "계약 중", "잔금·입주 당일", "계약 후", "보관할 자료"]) {
      expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    }
    expect(screen.getByRole("heading", { name: "주요 금전피해 유형 비교" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "전체 리포트 PDF 저장" })).toBeInTheDocument();
    expect(screen.getByLabelText("제출 자료 기준 피해 유형 비교 요약")).toBeInTheDocument();
    const questionGroup = screen.getByRole("heading", { name: "먼저 물어볼 질문" }).closest("section")!;
    expect(within(questionGroup).getAllByRole("listitem")).toHaveLength(3);
    fireEvent.click(within(questionGroup).getByRole("button", { name: /개 더 보기/ }));
    expect(within(questionGroup).getAllByRole("listitem").length).toBeGreaterThan(3);
    expect(within(questionGroup).getByRole("button", { name: "접기" })).toBeInTheDocument();
    expect(within(questionGroup).getAllByText("등기상 소유자와 계약자가 다른 이유와 계약 권한을 확인할 수 있는 서류를 보여주실 수 있나요?")).toHaveLength(1);

    expect(screen.queryByText("R01")).not.toBeInTheDocument();

    const j01 = screen.getByText("J01").closest("article");
    expect(j01).toHaveTextContent("상태: 불일치");
    expect(j01).toHaveTextContent("시급도: 즉시 확인");

    const j10 = screen.getByText("J10").closest("article");
    expect(j10).toHaveTextContent("상태: 명확");
    expect(j10).toHaveTextContent("보증금 반환 시점·조건 명확성");
  });

  it("keeps the report available with user-safe J10-J12 statuses after classification fallback", async () => {
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(fallbackDetail());

    renderPage();

    expect(await screen.findByRole("heading", { name: "12가지 계약 확인 결과" })).toBeInTheDocument();
    expandAllResultGroups();
    for (const judgmentId of ["J10", "J11", "J12"]) {
      const card = screen.getByText(judgmentId).closest("article");
      expect(card).toHaveTextContent("상태: 확인 필요");
    }
    expect(screen.getByRole("heading", { name: "방어 행동 허브" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("provider_unavailable");
    expect(document.body).not.toHaveTextContent("classification provider");
  });

  it("keeps rule results visible and shows a banner when only generation failed", async () => {
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(detail("failed"));

    renderPage();

    expect(await screen.findByText(/규칙 판정은 정상이며 안내 생성에 실패했습니다/)).toBeInTheDocument();
    expandAllResultGroups();
    expect(document.querySelectorAll(".result-card")).toHaveLength(12);
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

    expect(await screen.findByText("아직 생성된 리포트가 없습니다")).toBeInTheDocument();
  });
});
