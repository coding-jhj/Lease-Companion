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
    expect(document.querySelectorAll(".result-card")).toHaveLength(10);
    expect(screen.getByRole("heading", { name: "확인 질문과 다음 행동" })).toBeInTheDocument();
    expect(screen.getAllByText("안전한 기본 안내").length).toBeGreaterThan(0);
    expect(screen.getAllByText("등기상 소유자와 계약자가 다른 이유와 계약 권한을 확인할 수 있는 서류를 보여주실 수 있나요?")).toHaveLength(2);
    expect(screen.getAllByText("서명 또는 입금 전에 계약 권한과 관련 서류를 확인하세요.").length).toBeGreaterThan(0);

    const r01 = screen.getAllByText("R01")[0].closest("article");
    expect(r01).toHaveTextContent("상태: 불일치");
    expect(r01).toHaveTextContent("시급도: 즉시 확인");
    expect(r01).toHaveTextContent("이 결과만으로 사기·위법 여부를 판단할 수 없습니다.");
  });

  it("keeps rule results visible and shows a banner when only generation failed", async () => {
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(detail("failed"));

    renderPage();

    expect(await screen.findByText("규칙 판정은 정상이며 안내 생성에 실패했습니다.")).toBeInTheDocument();
    expect(document.querySelectorAll(".result-card")).toHaveLength(10);
    expect(screen.getByText("R01")).toBeInTheDocument();
  });
});