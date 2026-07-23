// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { PageShell } from "../../src/components/layout/PageShell";

afterEach(cleanup);

describe("PageShell logout", () => {
  it.each([
    ["계약 연습", "/practice", "계약 연습"],
    ["실전 계약 점검", "/contracts", "2 / 8"],
  ])("links the %s screen back to mode selection", (_label, path, step) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <PageShell step={step} title="진행 화면" description="진행 중"><p>본문</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "모드 선택" })).toHaveAttribute("href", "/choose-mode");
  });

  it("does not show a self-link on the mode selection screen", () => {
    render(
      <MemoryRouter initialEntries={["/choose-mode"]}>
        <PageShell step="시작" title="어떤 방식으로 시작할까요?" description="모드 선택"><p>선택</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: "모드 선택" })).not.toBeInTheDocument();
  });

  it("returns authenticated screens to login", () => {
    render(
      <MemoryRouter initialEntries={["/contracts"]}>
        <Routes>
          <Route path="/contracts" element={<PageShell step="2 / 8" title="내 계약" description="계약 목록"><p>대시보드</p></PageShell>} />
          <Route path="/login" element={<p>로그인 화면</p>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "로그아웃" }));
    expect(screen.getByText("로그인 화면")).toBeInTheDocument();
  });

  it("can hide logout on authentication screens", () => {
    render(
      <MemoryRouter>
        <PageShell step="1 / 8" title="로그인" description="로그인 화면" showLogout={false}><p>인증</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("button", { name: "로그아웃" })).not.toBeInTheDocument();
  });

  it("applies the requested responsive layout variant", () => {
    render(
      <MemoryRouter>
        <PageShell layout="workspace" step="2 / 8" title="내 계약" description="계약 목록"><p>대시보드</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("main")).toHaveClass("app-shell", "app-shell--workspace");
  });
});
