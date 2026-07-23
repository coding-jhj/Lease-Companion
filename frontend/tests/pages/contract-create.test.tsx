// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ContractCreatePage } from "../../src/pages/contract-create/ContractCreatePage";
import { mvpService } from "../../src/services/mvpService";
import type { ContractSummaryDto } from "../../src/types/api";

function LocationDisplay() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}

function renderContractCreate() {
  return render(
    <MemoryRouter initialEntries={["/contracts/new"]}>
      <LocationDisplay />
      <Routes>
        <Route path="/contracts/new" element={<ContractCreatePage />} />
        <Route path="/contracts/:contractId/situation" element={<p>계약 상황</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

function contract(id: number): ContractSummaryDto {
  return {
    id,
    title: "신림동 원룸 전세",
    contract_type: null,
    contract_stage: null,
    deposit_paid: null,
    signed: null,
    move_in_date: null,
    balance_payment_date: null,
    is_proxy_contract: null,
    registry_case_id: null,
    created_at: "2026-07-23T00:00:00Z",
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ContractCreatePage", () => {
  it("explains the contract name and reports an inline error", async () => {
    const createContract = vi.spyOn(mvpService, "createContract");
    renderContractCreate();

    expect(screen.getByText("집 등록")).toBeInTheDocument();
    expect(screen.getByText(/여러 계약을 구분하기 위한 이름/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "다음: 내 상황 알려주기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "나중에 알아볼 수 있도록 계약 이름을 입력해 주세요.",
    );
    expect(createContract).not.toHaveBeenCalled();
  });

  it("shows the second step and example placeholder", () => {
    renderContractCreate();

    expect(screen.getByText("2 / 8")).toBeInTheDocument();
    expect(screen.getByLabelText(/계약 이름/)).toHaveAttribute("placeholder", "예: 신림동 원룸 전세");
  });

  it("trims a valid title and moves to its situation page", async () => {
    const createContract = vi.spyOn(mvpService, "createContract").mockResolvedValue(contract(37));
    renderContractCreate();

    fireEvent.change(screen.getByLabelText(/계약 이름/), { target: { value: "  신림동 원룸 전세  " } });
    fireEvent.click(screen.getByRole("button", { name: "다음: 내 상황 알려주기" }));

    await waitFor(() => expect(createContract).toHaveBeenCalledWith("신림동 원룸 전세"));
    expect(await screen.findByTestId("location")).toHaveTextContent("/contracts/37/situation");
  });
});
