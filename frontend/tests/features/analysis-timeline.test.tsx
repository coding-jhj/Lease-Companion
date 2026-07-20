// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AnalysisTimeline } from "../../src/features/analysis-progress/AnalysisTimeline";

afterEach(cleanup);

describe("AnalysisTimeline", () => {
  it.each([
    ["request", "분석 요청 접수"],
    ["analysis", "규칙 판정·공식 근거 정리"],
    ["generation", "질문·행동 안내 생성"],
    ["complete", "리포트 준비 완료"],
  ] as const)("marks %s as the current stage", (activeStage, currentTitle) => {
    render(<AnalysisTimeline activeStage={activeStage} />);

    const current = screen.getByText(currentTitle).closest("li");
    expect(current).toHaveAttribute("aria-current", "step");
    expect(within(current!).getByText("진행 중")).toBeInTheDocument();
  });

  it("shows an honest delayed state without inventing another backend stage", () => {
    render(<AnalysisTimeline activeStage="generation" delayed />);

    const current = screen.getByText("질문·행동 안내 생성").closest("li");
    expect(within(current!).getByText("확인 지연")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
  });

  it("marks the active stage as needing attention after failure", () => {
    render(<AnalysisTimeline activeStage="analysis" hasError />);

    const current = screen.getByText("규칙 판정·공식 근거 정리").closest("li");
    expect(current).toHaveClass("analysis-timeline__step--error");
    expect(within(current!).getByText("확인 필요")).toBeInTheDocument();
  });
});
