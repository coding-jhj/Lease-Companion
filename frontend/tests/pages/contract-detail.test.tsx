// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

    const checkbox = await screen.findByLabelText(action.text);
    expect(checkbox).toBeChecked();
    expect(screen.getByText("계약서 · contract.pdf")).toBeInTheDocument();
    expect(screen.getByText(/completed/)).toBeInTheDocument();

    fireEvent.click(checkbox);
    await waitFor(() => expect(update).toHaveBeenCalledWith(1001, "checklist", action.item_key, false));
    expect(checkbox).not.toBeChecked();
  });
});
