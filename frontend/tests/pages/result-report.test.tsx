// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import analysisRunResultFixture from "../../../data/sample/fixtures/case-001/analysis_run_result.json";
import generationResultFixture from "../../../data/sample/fixtures/case-001/generation_result.json";
import extendedRuleResultsFixture from "../../../data/sample/fixtures/case-001/extended_rule_results.json";
import { ResultReportPage } from "../../src/pages/result-report/ResultReportPage";
import { mvpService } from "../../src/services/mvpService";
import type {
  AnalysisRunDetailDto,
  AnalysisRunResultDto,
  GenerationResultDto,
  RuleResultDto,
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
      results: [
        ...(analysisRunResultFixture as AnalysisRunResultDto).results,
        ...(extendedRuleResultsFixture as RuleResultDto[]),
      ],
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
    expect(await screen.findByRole("heading", { name: "임대인=등기 소유자 이름 일치" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "서두르지 않아도 괜찮아요." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "가장 먼저 확인할 항목으로 이동" })).toHaveAttribute("href", "#first-priority-group");
    expect(screen.getByRole("heading", { name: "전체 확인 결과" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "방어 행동 허브" })).toBeInTheDocument();
    expect(screen.getByLabelText("확인 우선순위 전체 개수")).toBeInTheDocument();
    expect(document.querySelectorAll(".result-card")).toHaveLength(36);
    for (const judgmentId of Array.from({ length: 12 }, (_, index) => `J${String(index + 1).padStart(2, "0")}`)) {
      expect(screen.getByText(judgmentId)).toBeInTheDocument();
    }
    for (const title of ["먼저 물어볼 질문", "서명 전 확인 행동", "계약 직후 행동", "보관할 자료"]) {
      expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    }
    expect(screen.getAllByText("등기상 소유자와 계약자가 다른 이유와 계약 권한을 확인할 수 있는 서류를 보여주실 수 있나요?")).toHaveLength(1);

    const r01 = screen.getAllByText("R01")[0].closest("article");
    expect(r01).toHaveTextContent("상태: 불일치");
    expect(r01).toHaveTextContent("시급도: 즉시 확인");
    expect(r01).toHaveTextContent("이 결과만으로 사기·위법 여부를 판단할 수 없습니다.");

    const j10 = screen.getByText("J10").closest("article");
    expect(j10).toHaveTextContent("상태: 명확");
    expect(j10).toHaveTextContent("보증금 반환 시점·조건 명확성");
  });

  it("keeps the report available with user-safe J10-J12 statuses after classification fallback", async () => {
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(fallbackDetail());

    renderPage();

    expect(await screen.findByRole("heading", { name: "전체 확인 결과" })).toBeInTheDocument();
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
    expect(document.querySelectorAll(".result-card")).toHaveLength(36);
    expect(screen.getByText("R01")).toBeInTheDocument();
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
