// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { PageShell } from "../../src/components/layout/PageShell";

afterEach(cleanup);

describe("PageShell logout", () => {
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
