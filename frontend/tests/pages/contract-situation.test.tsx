// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ContractSituationPage } from "../../src/pages/contract-create/ContractSituationPage";
import { mvpService } from "../../src/services/mvpService";

function LocationDisplay() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}

function renderSituationPage() {
  return render(
    <MemoryRouter initialEntries={["/contracts/1001/situation"]}>
      <LocationDisplay />
      <Routes>
        <Route path="/contracts/:contractId/situation" element={<ContractSituationPage />} />
        <Route path="/contracts/:contractId/upload" element={<p>문서 준비</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ContractSituationPage", () => {
  it("groups the situation form into three user questions with explicit answers", () => {
    renderSituationPage();

    expect(screen.getByRole("heading", { name: "어떤 계약을 준비하고 있나요?" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "지금 어디까지 진행했나요?" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "추가로 확인할 내용" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "전세" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "보증부 월세" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "일반 월세" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "계약금을 이미 지급했습니다 아니요" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "계약서에 이미 서명했습니다 아니요" })).toBeChecked();
    expect(screen.getByRole("button", { name: "다음: 문서 준비하기" })).toBeInTheDocument();
  });

  it("shows dates only after choosing to enter them and clears them when unknown", async () => {
    const saveSituation = vi.spyOn(mvpService, "saveSituation").mockResolvedValue({} as never);
    renderSituationPage();

    expect(screen.queryByLabelText("입주 예정일")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "날짜를 입력할게요" }));
    fireEvent.change(screen.getByLabelText("입주 예정일"), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText("잔금 지급 예정일"), { target: { value: "2026-08-25" } });
    fireEvent.click(screen.getByRole("button", { name: "아직 몰라요" }));

    expect(screen.queryByLabelText("입주 예정일")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "전세" }));
    fireEvent.click(screen.getByRole("button", { name: "다음: 문서 준비하기" }));

    await waitFor(() => expect(saveSituation).toHaveBeenCalledWith(1001, {
      contract_type: "전세",
      contract_stage: "계약금 입금 전",
      deposit_paid: false,
      signed: false,
      move_in_date: null,
      balance_payment_date: null,
      is_proxy_contract: null,
    }));
  });

  it("keeps date choices secondary and leaves the submit action as the only primary button", () => {
    renderSituationPage();

    expect(document.querySelectorAll("button.primary")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "날짜를 입력할게요" })).toHaveClass("secondary");
    fireEvent.click(screen.getByRole("button", { name: "날짜를 입력할게요" }));

    expect(screen.getByRole("button", { name: "아직 몰라요" })).toHaveClass("secondary");
    expect(screen.queryByRole("button", { name: "날짜 입력 닫기" })).not.toBeInTheDocument();
    expect(document.querySelectorAll("button.primary")).toHaveLength(1);
  });

  it("requires an explicit contract type before saving and focuses the first choice", async () => {
    const saveSituation = vi.spyOn(mvpService, "saveSituation").mockResolvedValue({} as never);
    renderSituationPage();

    fireEvent.click(screen.getByRole("button", { name: "다음: 문서 준비하기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("계약 유형을 선택해 주세요.");
    expect(screen.getByRole("radio", { name: "전세" })).toHaveFocus();
    expect(saveSituation).not.toHaveBeenCalled();
  });

  it("shows proxy-document guidance only when another person contracts for the landlord", () => {
    renderSituationPage();

    expect(screen.queryByText("위임장")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "집주인 대신 다른 사람이 계약해요" }));

    expect(screen.getByText("위임장")).toBeInTheDocument();
    expect(screen.getByText("인감증명서")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "집주인이 직접 계약해요" }));
    expect(screen.queryByText("위임장")).not.toBeInTheDocument();
  });

  it("saves the existing payload and allows retry after a save error", async () => {
    const saveSituation = vi.spyOn(mvpService, "saveSituation")
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce({} as never);
    renderSituationPage();

    fireEvent.click(screen.getByRole("radio", { name: "전세" }));
    fireEvent.click(screen.getByRole("radio", { name: "계약서를 받았고 서명 전이에요" }));
    fireEvent.click(screen.getByRole("button", { name: "다음: 문서 준비하기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("저장하지 못했습니다. 다시 시도해 주세요.");
    fireEvent.click(screen.getByRole("button", { name: "다음: 문서 준비하기" }));

    await waitFor(() => expect(saveSituation).toHaveBeenLastCalledWith(1001, {
      contract_type: "전세",
      contract_stage: "서명 전",
      deposit_paid: false,
      signed: false,
      move_in_date: null,
      balance_payment_date: null,
      is_proxy_contract: null,
    }));
    expect(await screen.findByTestId("location")).toHaveTextContent("/contracts/1001/upload");
  });
});
