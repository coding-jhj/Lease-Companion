// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthPage } from "../../src/pages/auth/AuthPage";
import { ContractPreparationPage } from "../../src/pages/contract-preparation/ContractPreparationPage";
import { ModeSelectPage } from "../../src/pages/mode-select/ModeSelectPage";
import { SituationSelectPage } from "../../src/pages/mode-select/SituationSelectPage";
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

    expect(await screen.findByRole("heading", { name: "어떻게 시작할까요?" })).toBeInTheDocument();
  });

  it("routes the mode cards to real check and practice", () => {
    render(<MemoryRouter><ModeSelectPage /></MemoryRouter>);

    expect(screen.getByRole("link", { name: /실전 계약 점검/ })).toHaveAttribute("href", "/start");
    expect(screen.getByRole("link", { name: /계약 연습 시뮬레이션/ })).toHaveAttribute("href", "/practice");
  });

  it("opens the situation screen from the real-check mode card", async () => {
    render(
      <MemoryRouter initialEntries={["/choose-mode"]}>
        <Routes>
          <Route path="/choose-mode" element={<ModeSelectPage />} />
          <Route path="/start" element={<SituationSelectPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("link", { name: /실전 계약 점검/ }));

    expect(await screen.findByRole("heading", { name: "지금 어떤 상황인가요?" })).toBeInTheDocument();
  });
});

describe("situation selection", () => {
  it("routes by the renter's current situation", () => {
    render(<MemoryRouter><SituationSelectPage /></MemoryRouter>);

    expect(screen.getByRole("link", { name: /아직 계약서를 받지 않았어요/ })).toHaveAttribute("href", "/prepare");
    expect(screen.getByRole("link", { name: /계약서 초안을 받았어요/ })).toHaveAttribute("href", "/contracts/new");
    expect(screen.queryByRole("link", { name: /이미 계약했어요/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /모드 다시 선택/ })).toHaveAttribute("href", "/choose-mode");
  });

  it("opens the preparation page from the first situation card", async () => {
    render(
      <MemoryRouter initialEntries={["/start"]}>
        <Routes>
          <Route path="/start" element={<SituationSelectPage />} />
          <Route path="/prepare" element={<ContractPreparationPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("link", { name: /아직 계약서를 받지 않았어요/ }));

    expect(await screen.findByRole("heading", {
      name: "계약 전, 금전 피해와 분쟁을 줄이는 준비",
    })).toBeInTheDocument();
  });
});
