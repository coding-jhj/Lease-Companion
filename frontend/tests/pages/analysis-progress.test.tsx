// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalysisProgressPage } from "../../src/pages/analysis-progress/AnalysisProgressPage";
import { mvpService } from "../../src/services/mvpService";
import type { AnalysisRunDetailDto, AsyncRunStatus } from "../../src/types/api";
import { LOCAL_MVP_POLL_TIMEOUT_MS, POLL_INTERVAL_MS } from "../../src/utils/pollUntilTerminal";

function run(status: AsyncRunStatus, error: string | null = null): AnalysisRunDetailDto {
  return {
    analysis_run_id: "RUN-1001-001",
    input_snapshot_id: "SNAP-1001",
    status,
    error,
    created_at: "2026-07-16T00:00:00Z",
    result: null,
    generation_result: null,
    generation_status: status === "completed" ? "completed" : null,
    generation_error: null,
  };
}

function renderPage(initialEntry = "/contracts/1001/analyzing") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/contracts/:contractId/analyzing" element={<AnalysisProgressPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function renderStrictPage() {
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={["/contracts/1001/analyzing"]}>
        <Routes>
          <Route path="/contracts/:contractId/analyzing" element={<AnalysisProgressPage />} />
        </Routes>
      </MemoryRouter>
    </StrictMode>,
  );
}

async function flushPromises() {
  await act(async () => {
    await Promise.resolve();
  });
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("AnalysisProgressPage", () => {
  it("resumes the supplied analysis run without starting a duplicate run", async () => {
    const start = vi.spyOn(mvpService, "startAnalysis");
    const getRun = vi.spyOn(mvpService, "getAnalysisRun").mockResolvedValue(run("completed"));

    renderPage("/contracts/1001/analyzing?analysisRunId=RUN-SUPPLIED-001");
    await flushPromises();

    expect(start).not.toHaveBeenCalled();
    expect(getRun).toHaveBeenCalledWith(1001, "RUN-SUPPLIED-001", expect.anything());
    expect(screen.getByRole("heading", { name: "확인 결과 준비 완료", level: 1 }))
      .toBeInTheDocument();
  });

  it("starts only one analysis run under React StrictMode", async () => {
    vi.useFakeTimers();
    const start = vi.spyOn(mvpService, "startAnalysis").mockResolvedValue(run("pending"));
    vi.spyOn(mvpService, "getAnalysisRun").mockResolvedValue(run("completed"));

    renderStrictPage();
    await flushPromises();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);
    });

    expect(start).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("heading", { name: "확인 결과 준비 완료", level: 1 })).toBeInTheDocument();
  });

  it("keeps backend failure details out of the user-facing retry guidance", async () => {
    vi.useFakeTimers();
    const start = vi.spyOn(mvpService, "startAnalysis")
      .mockResolvedValueOnce(run("pending"))
      .mockResolvedValueOnce(run("completed"));
    vi.spyOn(mvpService, "getAnalysisRun").mockResolvedValue(run("failed", "provider_timeout for case_id=CASE-001"));

    renderPage();
    await flushPromises();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);
    });

    expect(screen.getByRole("alert")).toHaveTextContent("확인 결과를 준비하지 못했습니다. 입력한 계약 정보는 그대로 저장되어 있습니다. 다시 시도해 주세요.");
    expect(screen.getByRole("alert")).not.toHaveTextContent("provider_timeout");
    expect(screen.getByRole("alert")).not.toHaveTextContent("case_id");
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    await flushPromises();

    expect(start).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("heading", { name: "확인 결과 준비 완료", level: 1 })).toBeInTheDocument();
  });

  it("stops polling after timeout and retries by checking the existing run", async () => {
    vi.useFakeTimers();
    const start = vi.spyOn(mvpService, "startAnalysis").mockResolvedValue(run("pending"));
    const getRun = vi.spyOn(mvpService, "getAnalysisRun").mockResolvedValue(run("pending"));

    renderPage();
    await flushPromises();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LOCAL_MVP_POLL_TIMEOUT_MS);
    });

    expect(screen.getByRole("alert")).toHaveTextContent("처리가 예상보다 오래 걸리고 있습니다.");
    const callsAtTimeout = getRun.mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 5);
    });
    expect(getRun).toHaveBeenCalledTimes(callsAtTimeout);

    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    await flushPromises();

    expect(start).toHaveBeenCalledTimes(1);
    expect(getRun.mock.calls.length).toBeGreaterThan(callsAtTimeout);
    expect(getRun).toHaveBeenLastCalledWith(1001, "RUN-1001-001", expect.anything());
  });

  it("does not make another polling request after unmount", async () => {
    vi.useFakeTimers();
    vi.spyOn(mvpService, "startAnalysis").mockResolvedValue(run("pending"));
    const getRun = vi.spyOn(mvpService, "getAnalysisRun").mockResolvedValue(run("pending"));

    const view = renderPage();
    await flushPromises();
    view.unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 5);
    });

    expect(getRun).not.toHaveBeenCalled();
  });

  it("waits for generation to become terminal after rule analysis completes", async () => {
    vi.useFakeTimers();
    const generationRunning = { ...run("completed"), generation_status: "running" as const };
    const generationCompleted = { ...run("completed"), generation_status: "completed" as const };
    vi.spyOn(mvpService, "startAnalysis").mockResolvedValue(run("pending"));
    const getRun = vi.spyOn(mvpService, "getAnalysisRun")
      .mockResolvedValueOnce(generationRunning)
      .mockResolvedValueOnce(generationCompleted);

    renderPage();
    await flushPromises();
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS); });
    expect(screen.getByRole("heading", { name: "확인 결과를 준비하고 있습니다" })).toBeInTheDocument();

    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS); });
    expect(screen.getByRole("heading", { name: "확인 결과 준비 완료", level: 1 })).toBeInTheDocument();
    expect(getRun).toHaveBeenCalledTimes(2);
  });
});
