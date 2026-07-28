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
    ["실전 계약 점검", "/contracts", "2 / 7"],
  ])("links the %s screen back to mode selection", (_label, path, step) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <PageShell step={step} title="진행 화면" description="진행 중"><p>본문</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "처음으로" })).toHaveAttribute("href", "/contracts");
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
          <Route path="/contracts" element={<PageShell step="2 / 7" title="내 계약" description="계약 목록"><p>대시보드</p></PageShell>} />
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
        <PageShell step="1 / 7" title="로그인" description="로그인 화면" showLogout={false}><p>인증</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("button", { name: "로그아웃" })).not.toBeInTheDocument();
  });

  it("applies the requested responsive layout variant", () => {
    render(
      <MemoryRouter>
        <PageShell layout="workspace" step="2 / 7" title="내 계약" description="계약 목록"><p>대시보드</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("main")).toHaveClass("app-shell", "app-shell--workspace");
  });

  it("derives the current step label and next action from the step number", () => {
    render(
      <MemoryRouter>
        <PageShell step="3 / 7" title="문서 올리기" description="문서 준비"><p>본문</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("progressbar", { name: /3 \/ 7단계/ })).toHaveAttribute("aria-valuenow", "3");
    const journey = screen.getByRole("navigation", { name: "계약 확인 진행 단계" });
    for (const label of ["시작 방법", "집 등록", "문서 준비", "내용 확인", "결과 준비", "확인 결과", "다음 행동"]) {
      expect(journey).toHaveTextContent(label);
    }
  });

  it("shows the full journey horizontally with the current step marked", () => {
    render(
      <MemoryRouter>
        <PageShell
          step="4 / 7"
          journey={{ current: 4, currentLabel: "문서 내용 확인", nextLabel: "확인 결과 준비" }}
          title="문서에서 읽은 내용 확인하기"
          description="중요한 내용부터 하나씩 확인합니다."
        >
          <p>내용</p>
        </PageShell>
      </MemoryRouter>,
    );

    expect(screen.getByText("시작 방법")).toBeInTheDocument();
    expect(screen.getByText("집 등록")).toBeInTheDocument();
    expect(screen.getByText("내용 확인").parentElement).toHaveAttribute("aria-current", "step");
  });

  it("links back to the previous step and to completed steps only", () => {
    render(
      <MemoryRouter initialEntries={["/contracts/12/review"]}>
        <PageShell step="4 / 7" title="문서에서 읽은 내용 확인" description="확인"><p>내용</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /이전 단계/ })).toHaveAttribute("href", "/contracts/12/upload");

    expect(screen.getByRole("link", { name: /집 등록/ })).toHaveAttribute("href", "/contracts");
    expect(screen.getByRole("link", { name: /문서 준비/ })).toHaveAttribute("href", "/contracts/12/upload");
    // 현재·예정 단계는 이동 링크를 만들지 않는다.
    expect(screen.queryByRole("link", { name: /내용 확인/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /확인 결과/ })).not.toBeInTheDocument();
  });

  it("skips the analysis step when walking back from the report", () => {
    render(
      <MemoryRouter initialEntries={["/contracts/12/report"]}>
        <PageShell step="6 / 7" title="내 계약 확인 결과" description="결과"><p>내용</p></PageShell>
      </MemoryRouter>,
    );

    // 5단계(결과 준비)는 되돌아갈 수 없으므로 4단계 내용 확인으로 건너뛴다.
    expect(screen.getByRole("link", { name: /이전 단계/ })).toHaveAttribute("href", "/contracts/12/review");
  });

  // 집 등록 바로 앞 화면은 상황 선택(/start)이다. /choose-mode로 보내면 두 화면 뒤로 건너뛴다.
  it("walks back one screen at a time from the contract registration step", () => {
    render(
      <MemoryRouter initialEntries={["/contracts/new"]}>
        <PageShell step="2 / 7" title="확인할 집 등록하기" description="등록"><p>내용</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /이전 단계/ })).toHaveAttribute("href", "/start");
  });

  it("shows a standalone back link on screens without the journey bar", () => {
    render(
      <MemoryRouter initialEntries={["/practice"]}>
        <PageShell step="계약 연습" title="계약 연습" description="연습" showJourney={false} backTo="/choose-mode" backLabel="모드 다시 선택">
          <p>내용</p>
        </PageShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /모드 다시 선택/ })).toHaveAttribute("href", "/choose-mode");
  });

  it("hides the previous-step link on the first step", () => {
    render(
      <MemoryRouter initialEntries={["/choose-mode"]}>
        <PageShell step="1 / 7" title="시작 방법" description="선택"><p>내용</p></PageShell>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: /이전 단계/ })).not.toBeInTheDocument();
  });

  it("keeps every journey display hidden when showJourney is false", () => {
    render(
      <MemoryRouter>
        <PageShell
          step="4 / 7"
          journey={{ current: 4, currentLabel: "문서 내용 확인", nextLabel: "확인 결과 준비" }}
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
    expect(screen.queryByRole("button", { name: "전체 과정 보기" })).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "계약 확인 진행 단계" })).not.toBeInTheDocument();
  });
});
