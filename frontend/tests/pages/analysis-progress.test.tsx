// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalysisProgressPage } from "../../src/pages/analysis-progress/AnalysisProgressPage";
import { mvpService } from "../../src/services/mvpService";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AnalysisProgressPage", () => {
  it("shows analyzing and completed states", async () => {
    let resolveAnalysis!: (value: { analysis_run_id: string }) => void;
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

    expect(screen.getByRole("heading", { name: "계약 내용을 확인하고 있어요" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "분석 중…" })).toBeDisabled();

    resolveAnalysis({ analysis_run_id: "RUN-1001-001" });

    expect(await screen.findByRole("heading", { name: "분석 준비 완료" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "리포트 보기" })).toBeEnabled();
  });
});
