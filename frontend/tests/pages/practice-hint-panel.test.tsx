// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PracticeHintPanel } from "../../src/pages/practice/PracticeHintPanel";

afterEach(cleanup);

describe("PracticeHintPanel", () => {
  it("reveals direction, confirmation target, and example sentence one step at a time", () => {
    render(<PracticeHintPanel guide="확인할 내용과 보류 의사를 전달하면 됩니다." prompt="계약을 바로 진행하시겠습니까?" />);

    expect(screen.getByText("방향")).toBeInTheDocument();
    expect(screen.getByText("확인할 내용과 보류 의사를 전달하면 됩니다.")).toBeInTheDocument();
    expect(screen.queryByText("확인 대상")).not.toBeInTheDocument();
    expect(screen.queryByText("예시 문장")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "다음 힌트" }));
    expect(screen.getByText("확인 대상")).toBeInTheDocument();
    expect(screen.getByText("계약을 바로 진행하시겠습니까?")).toBeInTheDocument();
    expect(screen.queryByText("예시 문장")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "다음 힌트" }));
    expect(screen.getByText("예시 문장")).toBeInTheDocument();
    expect(screen.getByText("바로 결정하기 전에 필요한 내용을 확인하겠습니다.")).toBeInTheDocument();
    expect(screen.queryByText(/정답표|숨은 신호|TURN-/)).not.toBeInTheDocument();
  });
});
