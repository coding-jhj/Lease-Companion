// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";
import { PracticeSimulationPage } from "../../src/pages/practice-simulation/PracticeSimulationPage";

afterEach(cleanup);

async function reachDialogue() {
  render(<MemoryRouter><PracticeSimulationPage /></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: "계약서 확인하기" }));
  fireEvent.click(screen.getByRole("button", { name: "계약서 확인 완료" }));
  fireEvent.click(screen.getByRole("button", { name: "시뮬레이션 시작" }));
}

describe("PracticeSimulationPage", () => {
  it("does not reveal or visually label the hidden clause before dialogue", async () => {
    render(<MemoryRouter><PracticeSimulationPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "계약서 확인하기" }));

    const contract = screen.getByRole("region", { name: "모의 계약서 요약" });
    expect(within(contract).getByText(/후임 임차인의 보증금이 입금된 후 반환/)).toBeInTheDocument();
    expect(within(contract).queryByText(/위험|정답|문제 특약/)).not.toBeInTheDocument();
  });

  it("branches on a user question and cites the utterance in the score-free debrief", async () => {
    await reachDialogue();

    const input = screen.getByLabelText("직접 질문하거나 요청하기");
    fireEvent.change(input, { target: { value: "후임 임차인이 안 구해지면 어떻게 되나요?" } });
    fireEvent.click(screen.getByRole("button", { name: "말하기" }));

    expect(screen.getByText(/지금까지는 대부분 금방 구해졌습니다/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "대화를 마치고 최종 행동 선택" }));
    fireEvent.click(screen.getByRole("button", { name: "계약 보류" }));

    expect(screen.getByText("내 대화 복기")).toBeInTheDocument();
    expect(screen.getAllByText(/후임 임차인이 안 구해지면 어떻게 되나요/).length).toBeGreaterThan(0);
    expect(screen.getByText(/안전·위험 여부나 체결 권고가 아니라/)).toBeInTheDocument();
    expect(screen.queryByText(/안전 점수|위험 점수|사기 가능성 점수/)).not.toBeInTheDocument();
  });

  it("shows the revision wording only after the user selects revision request", async () => {
    await reachDialogue();
    expect(screen.queryByText(/후임 임차인의 계약 체결 또는 보증금 입금 여부는 반환 조건으로 하지 않는다/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "대화를 마치고 최종 행동 선택" }));
    fireEvent.click(screen.getByRole("button", { name: "특약 수정을 다시 요구" }));

    expect(screen.getByText(/후임 임차인의 계약 체결 또는 보증금 입금 여부는 반환 조건으로 하지 않는다/)).toBeInTheDocument();
  });
});
