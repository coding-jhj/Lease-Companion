// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
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
    result: analysisRunResultFixture as AnalysisRunResultDto,
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
  it("renders R01-R10 and generated guidance with a safe fallback label", async () => {
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(detail());

    renderPage();

    expect(screen.getByText("리포트를 불러오는 중")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "임대인=등기 소유자 이름 일치" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "핵심 규칙 판정" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "조항 명확성 판정" })).toBeInTheDocument();
    expect(document.querySelectorAll(".result-card")).toHaveLength(13);
    expect(screen.getByRole("heading", { name: "확인 질문과 다음 행동" })).toBeInTheDocument();
    expect(screen.getAllByText("안전한 기본 안내").length).toBeGreaterThan(0);
    expect(screen.getAllByText("등기상 소유자와 계약자가 다른 이유와 계약 권한을 확인할 수 있는 서류를 보여주실 수 있나요?")).toHaveLength(2);
    expect(screen.getAllByText("서명 또는 입금 전에 계약 권한과 관련 서류를 확인하세요.").length).toBeGreaterThan(0);

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

    expect(await screen.findByRole("heading", { name: "조항 명확성 판정" })).toBeInTheDocument();
    for (const judgmentId of ["J10", "J11", "J12"]) {
      const card = screen.getByText(judgmentId).closest("article");
      expect(card).toHaveTextContent("상태: 확인 필요");
    }
    expect(screen.getByRole("heading", { name: "핵심 규칙 판정" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "확인 질문과 다음 행동" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("provider_unavailable");
    expect(document.body).not.toHaveTextContent("classification provider");
  });

  it("keeps rule results visible and shows a banner when only generation failed", async () => {
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(detail("failed"));

    renderPage();

    expect(await screen.findByText("규칙 판정은 정상이며 안내 생성에 실패했습니다.")).toBeInTheDocument();
    expect(document.querySelectorAll(".result-card")).toHaveLength(13);
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
