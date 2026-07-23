// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "../../src/pages/dashboard/DashboardPage";
import { mvpService } from "../../src/services/mvpService";
import type { ContractSummaryDto } from "../../src/types/api";

function contract(id: number, title: string, action_status: ContractSummaryDto["action_status"]): ContractSummaryDto {
  return {
    id, title,
    contract_type: null, contract_stage: null, deposit_paid: null, signed: null,
    move_in_date: null, balance_payment_date: null, is_proxy_contract: null,
    registry_case_id: null, created_at: "2026-07-21T00:00:00Z", action_status,
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("DashboardPage grouping", () => {
  it("keeps only the new contract action below the contract list", async () => {
    vi.spyOn(mvpService, "getContracts").mockResolvedValue([]);

    render(<MemoryRouter><DashboardPage /></MemoryRouter>);

    expect(await screen.findByRole("link", { name: "새 계약 점검 시작" })).toHaveAttribute("href", "/contracts/new");
    expect(screen.queryByText("실전 계약 점검 모드")).not.toBeInTheDocument();
    expect(screen.queryByText("계약 연습 시뮬레이션 모드")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "계약 연습 시작" })).not.toBeInTheDocument();
  });

  it("splits contracts into action groups and collapses completed ones", async () => {
    vi.spyOn(mvpService, "getContracts").mockResolvedValue([
      contract(1, "미행동 계약건", "none"),
      contract(2, "행동중 계약건", "in_progress"),
      contract(3, "완료 계약건", "done"),
    ]);

    render(<MemoryRouter><DashboardPage /></MemoryRouter>);

    const notStarted = await screen.findByRole("region", { name: "점검을 시작하지 않은 계약 1개" });
    expect(within(notStarted).getByText("미행동 계약건")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "확인 중인 계약 1개" })).getByText("행동중 계약건")).toBeInTheDocument();

    // 행동 완료 그룹은 기본 접힌 details (완료 계약은 숨겨두고 펼쳐서 확인).
    const doneDetails = screen.getByText("확인을 마친 계약 1개").closest("details");
    expect(doneDetails).not.toHaveAttribute("open");
    expect(within(doneDetails as HTMLElement).getByText("완료 계약건")).toBeInTheDocument();
  });
});

describe("DashboardPage delete", () => {
  it("deletes a contract after confirmation and reloads the list", async () => {
    const getContracts = vi
      .spyOn(mvpService, "getContracts")
      .mockResolvedValueOnce([contract(7, "행복빌라 302호 전세", "none")])
      .mockResolvedValueOnce([]);
    const deleteContract = vi.spyOn(mvpService, "deleteContract").mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    await screen.findByText("행복빌라 302호 전세");

    fireEvent.click(screen.getByRole("button", { name: "계약 삭제" }));

    await waitFor(() => expect(deleteContract).toHaveBeenCalledWith(7));
    expect(getContracts).toHaveBeenCalledTimes(2); // 삭제 후 목록 재조회
    await waitFor(() =>
      expect(screen.queryByText("행복빌라 302호 전세")).not.toBeInTheDocument(),
    );
  });

  it("does not delete when confirmation is cancelled", async () => {
    vi.spyOn(mvpService, "getContracts").mockResolvedValue([contract(7, "행복빌라 302호 전세", "none")]);
    const deleteContract = vi.spyOn(mvpService, "deleteContract").mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(false);

    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    await screen.findByText("행복빌라 302호 전세");

    fireEvent.click(screen.getByRole("button", { name: "계약 삭제" }));

    expect(deleteContract).not.toHaveBeenCalled();
  });
});
