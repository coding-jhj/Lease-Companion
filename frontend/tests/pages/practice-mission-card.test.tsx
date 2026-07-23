// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PracticeMissionCard } from "../../src/pages/practice/PracticeMissionCard";

afterEach(cleanup);

describe("PracticeMissionCard", () => {
  it("shows progress toward the declared target for a supported scenario", () => {
    render(<PracticeMissionCard scenarioId="PRACTICE-DEFERRED-REFUND-001" confirmedCount={2} />);
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "미션 진행률" })).toHaveAttribute("aria-valuemax", "3");
  });

  it("clamps progress to the declared target", () => {
    render(<PracticeMissionCard scenarioId="PRACTICE-PROXY-AUTHORITY-001" confirmedCount={9} />);
    expect(screen.getByText("3 / 3")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "미션 진행률" })).toHaveAttribute("aria-valuenow", "3");
  });

  it("does not fabricate a denominator for the inactive broker-pressure fixture", () => {
    render(<PracticeMissionCard scenarioId="PRACTICE-BROKER-PRESSURE-001" confirmedCount={4} />);
    // 목표 수가 공개 메타데이터에 없으면 잘못된 100% 진행률을 만들지 않는다.
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByText(/\/\s*3/)).not.toBeInTheDocument();
    expect(screen.getByText("4개 확인")).toBeInTheDocument();
  });

  it("does not show progress for an unregistered scenario", () => {
    render(<PracticeMissionCard scenarioId="PRACTICE-UNKNOWN-999" confirmedCount={7} />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.getByText("7개 확인")).toBeInTheDocument();
  });

  it("hides all progress before the session starts", () => {
    render(<PracticeMissionCard scenarioId="PRACTICE-DEFERRED-REFUND-001" />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.getByText("오늘의 미션")).toBeInTheDocument();
  });
});
