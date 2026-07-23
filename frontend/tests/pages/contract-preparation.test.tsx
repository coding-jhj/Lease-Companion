// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ContractPreparationPage } from "../../src/pages/contract-preparation/ContractPreparationPage";

const originalClipboard = navigator.clipboard;

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: originalClipboard });
});

describe("ContractPreparationPage", () => {
  it("offers preparation actions without creating a contract", () => {
    render(<MemoryRouter><ContractPreparationPage /></MemoryRouter>);

    expect(screen.getByRole("heading", { name: "계약 전에 세 가지만 준비해 보세요" })).toBeInTheDocument();
    expect(screen.getByText("집을 볼 때")).toBeInTheDocument();
    expect(screen.getByText("계약서 초안을 요청할 때")).toBeInTheDocument();
    expect(screen.getByText("가계약금을 보내기 전에")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "이 상황을 연습해 볼게요" })).toHaveAttribute("href", "/practice");
    expect(screen.getByRole("link", { name: "계약서 초안을 받았어요" })).toHaveAttribute("href", "/contracts/new");
  });

  it("shows a status message after copying the draft request", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    render(<MemoryRouter><ContractPreparationPage /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "문구 복사" }));

    expect(await screen.findByRole("status")).toHaveTextContent("요청 문장을 복사했습니다.");
    expect(writeText).toHaveBeenCalledWith("서명하기 전에 계약서 내용을 먼저 확인하고 싶습니다. 초안을 보내주실 수 있을까요?");
  });

  it("shows an alert when copying the draft request is rejected", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    render(<MemoryRouter><ContractPreparationPage /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "문구 복사" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("문장을 복사하지 못했습니다. 직접 선택해 복사해 주세요.");
  });

  it("shows an alert when the clipboard is unavailable", async () => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
    render(<MemoryRouter><ContractPreparationPage /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "문구 복사" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("문장을 복사하지 못했습니다. 직접 선택해 복사해 주세요.");
  });
});
