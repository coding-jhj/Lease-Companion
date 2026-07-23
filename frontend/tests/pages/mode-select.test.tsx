// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthPage } from "../../src/pages/auth/AuthPage";
import { ContractPreparationPage } from "../../src/pages/contract-preparation/ContractPreparationPage";
import { ModeSelectPage } from "../../src/pages/mode-select/ModeSelectPage";
import { mvpService } from "../../src/services/mvpService";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("login mode selection", () => {
  it("moves a signed-in user to mode selection", async () => {
    vi.spyOn(mvpService, "login").mockResolvedValue({ access_token: "test-token", token_type: "bearer" });
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/choose-mode" element={<ModeSelectPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("아이디"), { target: { value: "tester" } });
    fireEvent.change(screen.getByLabelText("비밀번호"), { target: { value: "password1!" } });
    fireEvent.click(screen.getByRole("button", { name: "로그인하고 시작" }));

    expect(await screen.findByRole("heading", { name: "지금 어떤 상황인가요?" })).toBeInTheDocument();
  });

  it("routes by the renter's current situation", () => {
    render(<MemoryRouter><ModeSelectPage /></MemoryRouter>);

    expect(screen.getByRole("link", { name: /아직 계약서를 받지 않았어요/ })).toHaveAttribute("href", "/prepare");
    expect(screen.getByRole("link", { name: /계약서 초안을 받았어요/ })).toHaveAttribute("href", "/contracts/new");
    expect(screen.getByRole("link", { name: /이미 계약했어요/ })).toHaveAttribute("href", "/contracts");
    expect(screen.queryByText("모드 선택")).not.toBeInTheDocument();
  });

  it("opens the preparation page from the first situation card", async () => {
    render(
      <MemoryRouter initialEntries={["/choose-mode"]}>
        <Routes>
          <Route path="/choose-mode" element={<ModeSelectPage />} />
          <Route path="/prepare" element={<ContractPreparationPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("link", { name: /아직 계약서를 받지 않았어요/ }));

    expect(await screen.findByRole("heading", { name: "계약 전에 세 가지만 준비해 보세요" })).toBeInTheDocument();
  });
});
