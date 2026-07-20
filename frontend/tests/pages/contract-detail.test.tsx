// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import analysisRunResultFixture from "../../../data/sample/fixtures/case-001/analysis_run_result.json";
import generationResultFixture from "../../../data/sample/fixtures/case-001/generation_result.json";
import { ContractDetailPage } from "../../src/pages/contract-detail/ContractDetailPage";
import { mvpService } from "../../src/services/mvpService";
import type { AnalysisRunDetailDto, AnalysisRunResultDto, GenerationResultDto } from "../../src/types/api";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ContractDetailPage", () => {
  it("combines generated text with saved state and shows histories", async () => {
    const generation = generationResultFixture as GenerationResultDto;
    const action = generation.items[0].signing_checklist_items[0];
    const detail: AnalysisRunDetailDto = {
      analysis_run_id: "RUN-1001-001",
      input_snapshot_id: "SNAP-1001-001",
      status: "completed",
      error: null,
      created_at: "2026-07-18T00:00:00Z",
      result: analysisRunResultFixture as AnalysisRunResultDto,
      generation_result: generation,
      generation_status: "completed",
      generation_error: null,
    };
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(detail);
    vi.spyOn(mvpService, "getAnalysisRuns").mockResolvedValue([detail]);
    vi.spyOn(mvpService, "getDocuments").mockResolvedValue([
      { id: 1, doc_type: "계약서", filename: "contract.pdf", size_bytes: 100, created_at: "2026-07-18T00:00:00Z" },
    ]);
    vi.spyOn(mvpService, "getChecklist").mockResolvedValue([
      { kind: "checklist", item_key: action.item_key, done: true, updated_at: "2026-07-18T00:00:00Z" },
    ]);
    const update = vi.spyOn(mvpService, "updateChecklistItem").mockResolvedValue(
      { kind: "checklist", item_key: action.item_key, done: false, updated_at: "2026-07-18T01:00:00Z" },
    );

    render(
      <MemoryRouter initialEntries={["/contracts/1001"]}>
        <Routes><Route path="/contracts/:contractId" element={<ContractDetailPage />} /></Routes>
      </MemoryRouter>,
    );

    const completedSection = (await screen.findByRole("heading", { name: "완료된 체크리스트 항목" })).closest("section")!;
    expect(within(completedSection).getByText(action.text)).toBeInTheDocument();
    expect(screen.getByText("계약서 · contract.pdf")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /완료 리포트 보기/ })).toHaveAttribute(
      "href",
      "/contracts/1001/report?analysisRunId=RUN-1001-001",
    );

    fireEvent.click(within(completedSection).getByRole("button", { name: `${action.text} 확인 취소` }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(1001, "checklist", action.item_key, false));
    const pendingSection = screen.getByRole("heading", { name: "서명 전 체크리스트" }).closest("section")!;
    expect(within(pendingSection).getByRole("button", { name: `${action.text} 확인` })).toBeInTheDocument();
  });

  it("moves a confirmed signing item below and reveals post-contract actions", async () => {
    const generation = structuredClone(generationResultFixture) as GenerationResultDto;
    const signingAction = generation.items[0].signing_checklist_items[0];
    const postAction = {
      item_key: "R01:post_action:000000000001",
      text: "전입신고와 확정일자를 완료한다.",
    };
    generation.items[0].post_contract_action_items = [postAction];
    const detail: AnalysisRunDetailDto = {
      analysis_run_id: "RUN-1001-001",
      input_snapshot_id: "SNAP-1001-001",
      status: "completed",
      error: null,
      created_at: "2026-07-18T00:00:00Z",
      result: analysisRunResultFixture as AnalysisRunResultDto,
      generation_result: generation,
      generation_status: "completed",
      generation_error: null,
    };
    vi.spyOn(mvpService, "getAnalysisDetail").mockResolvedValue(detail);
    vi.spyOn(mvpService, "getAnalysisRuns").mockResolvedValue([]);
    vi.spyOn(mvpService, "getDocuments").mockResolvedValue([]);
    vi.spyOn(mvpService, "getChecklist").mockResolvedValue([]);
    const update = vi.spyOn(mvpService, "updateChecklistItem").mockImplementation(
      async (_contractId, kind, itemKey, done) => ({
        kind,
        item_key: itemKey,
        done,
        updated_at: "2026-07-18T01:00:00Z",
      }),
    );

    render(
      <MemoryRouter initialEntries={["/contracts/1001"]}>
        <Routes><Route path="/contracts/:contractId" element={<ContractDetailPage />} /></Routes>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("heading", { name: "완료된 체크리스트 항목" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "계약 직후 행동" })).not.toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: `${signingAction.text} 확인` }));

    await waitFor(() => expect(update).toHaveBeenCalledWith(1001, "checklist", signingAction.item_key, true));
    const completedSection = screen.getByRole("heading", { name: "완료된 체크리스트 항목" }).closest("section")!;
    expect(within(completedSection).getByText(signingAction.text)).toBeInTheDocument();
    const postActionSection = screen.getByRole("heading", { name: "계약 직후 행동" }).closest("section")!;
    expect(within(postActionSection).getByText(postAction.text)).toBeInTheDocument();
  });

  it("deletes after confirmation and returns to the dashboard", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(mvpService, "getChecklist").mockResolvedValue([]);
    vi.spyOn(mvpService, "getAnalysisDetail").mockRejectedValue(new Error("no completed run"));
    vi.spyOn(mvpService, "getAnalysisRuns").mockResolvedValue([]);
    vi.spyOn(mvpService, "getDocuments").mockResolvedValue([]);
    const deleteContract = vi.spyOn(mvpService, "deleteContract").mockResolvedValue(undefined);

    render(
      <MemoryRouter initialEntries={["/contracts/1001"]}>
        <Routes>
          <Route path="/contracts/:contractId" element={<ContractDetailPage />} />
          <Route path="/contracts" element={<p>대시보드 갱신 완료</p>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "계약 삭제" }));
    await waitFor(() => expect(deleteContract).toHaveBeenCalledWith(1001));
    expect(await screen.findByText("대시보드 갱신 완료")).toBeInTheDocument();
  });

  it("keeps the detail page available when deletion fails", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(mvpService, "getChecklist").mockResolvedValue([]);
    vi.spyOn(mvpService, "getAnalysisDetail").mockRejectedValue(new Error("no completed run"));
    vi.spyOn(mvpService, "getAnalysisRuns").mockResolvedValue([]);
    vi.spyOn(mvpService, "getDocuments").mockResolvedValue([]);
    vi.spyOn(mvpService, "deleteContract").mockRejectedValue(new Error("삭제 권한을 확인해 주세요."));

    render(
      <MemoryRouter initialEntries={["/contracts/1001"]}>
        <Routes><Route path="/contracts/:contractId" element={<ContractDetailPage />} /></Routes>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "계약 삭제" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("삭제 권한을 확인해 주세요.");
    expect(screen.getByRole("button", { name: "계약 삭제" })).toBeEnabled();
  });
});
