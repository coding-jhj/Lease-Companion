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

    expect(screen.getByRole("heading", { name: "계약 전, 금전 피해와 분쟁을 줄이는 준비" })).toBeInTheDocument();
    expect(screen.getByText("급하게 결정하지 않아도 괜찮아요")).toBeInTheDocument();
    expect(screen.getByText("집을 볼 때 유의할 점")).toBeInTheDocument();
    expect(screen.getByText("누수·곰팡이·결로·침수 흔적")).toBeInTheDocument();
    expect(screen.getByText("가계약하기 전에 자료 요청")).toBeInTheDocument();
    expect(screen.getByText("가계약금을 보내기 전에 다음 자료를 먼저 요청하세요.")).toBeInTheDocument();
    expect(screen.getByText("등기사항증명서")).toBeInTheDocument();
    expect(screen.getByText("계약서 초안 사본")).toBeInTheDocument();
    expect(screen.getByText("특약사항")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "주의할 점" })).toBeInTheDocument();
    expect(screen.getByText(/계약 성립 여부와 반환 조건을 둘러싼 분쟁/)).toBeInTheDocument();
    expect(screen.getByText(/자료와 조건을 확인할 때까지 송금을 보류/)).toBeInTheDocument();
    expect(screen.getByText("가계약금을 보내기 전에 확인하기")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "다음에 무엇을 해볼까요?" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "계약서 초안 등을 받아 점검해 보기" })).toHaveAttribute("href", "/contracts/new");
    expect(screen.getByRole("link", { name: "계약할 때 시뮬레이션 체험하러 가기" })).toHaveAttribute("href", "/practice");
  });

  // 로그인해야 들어오는 화면이라 머리말에서 나가는 길이 있어야 한다.
  it("keeps the header exits for a signed-in visitor", () => {
    render(<MemoryRouter><ContractPreparationPage /></MemoryRouter>);

    expect(screen.getByRole("link", { name: "처음으로" })).toHaveAttribute("href", "/choose-mode");
    expect(screen.getByRole("button", { name: "로그아웃" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /상황 다시 선택/ })).toHaveAttribute("href", "/start");
  });

  // 안내 항목이 12개라 전부 펼치면 화면이 길어진다. 제목은 다 보이고 첫 묶음만 펼쳐 둔다.
  it("opens only the first guidance card and keeps the rest collapsed", () => {
    const { container } = render(<MemoryRouter><ContractPreparationPage /></MemoryRouter>);

    const cards = [...container.querySelectorAll<HTMLDetailsElement>("details.preparation-card")];
    expect(cards).toHaveLength(3);
    expect(cards.map((card) => card.open)).toEqual([true, false, false]);
    for (const title of ["집을 볼 때 유의할 점", "가계약하기 전에 자료 요청", "가계약금을 보내기 전에 확인하기"]) {
      expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    }
    // 접힌 카드에도 안에 몇 개가 있는지 남는다.
    expect(cards.map((card) => card.querySelector(".preparation-card__count")?.textContent)).toEqual(["6개", "5개", "3개"]);
    // details가 만드는 익명 상자 대신 직접 감싼 상자가 내용 간격을 맡는다.
    for (const card of cards) expect(card.querySelector(".preparation-card__body")).not.toBeNull();
  });

  it("shows a status message after copying the draft request", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    render(<MemoryRouter><ContractPreparationPage /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "문구 복사" }));

    expect(await screen.findByRole("status")).toHaveTextContent("요청 문장을 복사했습니다.");
    expect(writeText).toHaveBeenCalledWith("가계약금을 보내기 전에 확인하고 싶습니다. 등기사항증명서, 계약서 초안 사본, 특약사항을 먼저 보내주실 수 있을까요?");
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
