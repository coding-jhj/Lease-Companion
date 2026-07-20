// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { render, screen, within } from "@testing-library/react";
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

afterEach(() => vi.restoreAllMocks());

describe("DashboardPage grouping", () => {
  it("splits contracts into action groups and collapses completed ones", async () => {
    vi.spyOn(mvpService, "getContracts").mockResolvedValue([
      contract(1, "미행동 계약건", "none"),
      contract(2, "행동중 계약건", "in_progress"),
      contract(3, "완료 계약건", "done"),
    ]);

    render(<MemoryRouter><DashboardPage /></MemoryRouter>);

    const notStarted = await screen.findByRole("region", { name: "미행동 계약 1개" });
    expect(within(notStarted).getByText("미행동 계약건")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "행동중 계약 1개" })).getByText("행동중 계약건")).toBeInTheDocument();

    // 행동 완료 그룹은 기본 접힌 details (완료 계약은 숨겨두고 펼쳐서 확인).
    const doneDetails = screen.getByText("행동 완료 계약 1개").closest("details");
    expect(doneDetails).not.toHaveAttribute("open");
    expect(within(doneDetails as HTMLElement).getByText("완료 계약건")).toBeInTheDocument();
  });
});
