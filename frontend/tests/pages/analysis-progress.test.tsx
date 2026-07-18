// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalysisProgressPage } from "../../src/pages/analysis-progress/AnalysisProgressPage";
import { mvpService } from "../../src/services/mvpService";
import type { AnalysisRunDetailDto } from "../../src/types/api";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AnalysisProgressPage", () => {
  it("shows analyzing and completed states", async () => {
    let resolveAnalysis!: (value: AnalysisRunDetailDto) => void;
    vi.spyOn(mvpService, "startAnalysis").mockReturnValue(
      new Promise((resolve) => {
        resolveAnalysis = resolve;
      }),
    );

    render(
      <MemoryRouter initialEntries={["/contracts/1001/analyzing"]}>
        <Routes>
          <Route path="/contracts/:contractId/analyzing" element={<AnalysisProgressPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "분석 시작을 기다리고 있어요" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "분석 중…" })).toBeDisabled();

    await act(async () => resolveAnalysis({
      analysis_run_id: "RUN-1001-001",
      input_snapshot_id: "SNAP-1001",
      status: "completed",
      error: null,
      created_at: "2026-07-16T00:00:00Z",
      result: null,
      generation_result: null,
      generation_status: null,
      generation_error: null,
    }));

    expect(await screen.findByRole("heading", { name: "분석 완료" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "리포트 보기" })).toBeEnabled();
  });
});
