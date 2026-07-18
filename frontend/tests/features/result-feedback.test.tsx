// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResultFeedback } from "../../src/features/result-feedback/ResultFeedback";
import { mvpService } from "../../src/services/mvpService";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ResultFeedback", () => {
  it("loads history and submits rating with feedback text", async () => {
    vi.spyOn(mvpService, "getFeedback").mockResolvedValue([
      { id: 1, contract_id: 1001, content: "기존 의견", rating: 4, created_at: "2026-07-18T00:00:00Z" },
    ]);
    const create = vi.spyOn(mvpService, "createFeedback").mockResolvedValue(
      { id: 2, contract_id: 1001, content: "설명이 이해하기 쉬워요", rating: 5, created_at: "2026-07-18T01:00:00Z" },
    );

    render(<ResultFeedback contractId={1001} />);
    expect(await screen.findByText("이전 의견 1건")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("평점"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("의견"), { target: { value: "설명이 이해하기 쉬워요" } });
    fireEvent.click(screen.getByRole("button", { name: "의견 저장" }));

    await waitFor(() => expect(create).toHaveBeenCalledWith(
      1001,
      { content: "설명이 이해하기 쉬워요", rating: 5 },
    ));
    expect(screen.getByRole("status")).toHaveTextContent("의견이 저장되었습니다.");
  });
});
