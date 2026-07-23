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

    expect(screen.getByRole("link", { name: "처음으로" })).toHaveAttribute("href", "/choose-mode");
  });

  it("does not show a self-link on the mode selection screen", () => {
    render(
      <MemoryRouter initialEntries={["/choose-mode"]}>
        <PageShell step="시작" title="어떤 방식으로 시작할까요?" description="모드 선택"><p>선택</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: "처음으로" })).not.toBeInTheDocument();
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

  it("describes progress with user actions instead of system processing terms", () => {
    render(
      <MemoryRouter>
        <PageShell step="4 / 8" title="문서 올리기" description="문서 준비"><p>본문</p></PageShell>
      </MemoryRouter>,
    );

    const journey = screen.getByRole("navigation", { name: "계약 확인 진행 단계" });
    for (const label of ["시작 방법", "집 등록", "상황 입력", "문서 준비", "내용 확인", "결과 준비", "확인 결과", "다음 행동"]) {
      expect(journey).toHaveTextContent(label);
    }
  });

  it("shows current and next actions before disclosing the full journey", () => {
    render(
      <MemoryRouter>
        <PageShell
          step="5 / 8"
          journey={{ current: 5, currentLabel: "문서 내용 확인", nextLabel: "확인 결과 준비" }}
          title="문서에서 읽은 내용 확인하기"
          description="중요한 내용부터 하나씩 확인합니다."
        >
          <p>내용</p>
        </PageShell>
      </MemoryRouter>,
    );

    expect(screen.getByText("현재: 문서 내용 확인")).toBeInTheDocument();
    expect(screen.getByText("다음: 확인 결과 준비")).toBeInTheDocument();
    expect(screen.queryByText("시작 방법")).not.toBeInTheDocument();
    expect(screen.queryByText("집 등록")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("전체 과정 보기"));

    expect(screen.getByText("시작 방법")).toBeInTheDocument();
    expect(screen.getByText("집 등록")).toBeInTheDocument();
    expect(screen.getByText("내용 확인").parentElement).toHaveAttribute("aria-current", "step");
  });

  it("keeps every journey display hidden when showJourney is false", () => {
    render(
      <MemoryRouter>
        <PageShell
          step="5 / 8"
          journey={{ current: 5, currentLabel: "문서 내용 확인", nextLabel: "확인 결과 준비" }}
          title="준비 화면"
          description="진행 표시 없음"
          showJourney={false}
        >
          <p>내용</p>
        </PageShell>
      </MemoryRouter>,
    );

    expect(screen.queryByText("현재: 문서 내용 확인")).not.toBeInTheDocument();
    expect(screen.queryByText("다음: 확인 결과 준비")).not.toBeInTheDocument();
    expect(screen.queryByText("전체 과정 보기")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "계약 확인 진행 단계" })).not.toBeInTheDocument();
  });
});
