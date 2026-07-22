// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthPage } from "../../src/pages/auth/AuthPage";
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

    expect(await screen.findByRole("heading", { name: "어떤 방식으로 시작할까요?" })).toBeInTheDocument();
  });

  it("offers separate practice and real contract destinations", () => {
    render(<MemoryRouter><ModeSelectPage /></MemoryRouter>);

    expect(screen.getByRole("link", { name: "연습 시뮬레이션 시작" })).toHaveAttribute("href", "/practice/signing");
    expect(screen.getByRole("link", { name: "실전 계약 점검 시작" })).toHaveAttribute("href", "/contracts");
  });
});
