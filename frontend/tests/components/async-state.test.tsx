// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EmptyState, ErrorState, LoadingState } from "../../src/components/feedback/AsyncState";

describe("async state messages", () => {
  it("announces loading and empty states", () => {
    const { rerender } = render(<LoadingState title="불러오는 중" description="잠시 기다려 주세요." />);
    expect(screen.getByRole("status")).toHaveTextContent("불러오는 중");

    rerender(<EmptyState title="결과 없음" description="표시할 항목이 없습니다." />);
    expect(screen.getByRole("status")).toHaveTextContent("결과 없음");
  });

  it("shows an alert and retries", () => {
    const onRetry = vi.fn();
    render(<ErrorState title="불러오지 못했습니다" description="다시 시도해 주세요." onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
