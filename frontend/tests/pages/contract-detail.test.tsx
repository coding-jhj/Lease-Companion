// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import analysisRunResultFixture from "../../../data/sample/fixtures/case-001/analysis_run_result.json";
import generationResultFixture from "../../../data/sample/fixtures/case-001/generation_result.json";
import { standardPostActionFor } from "../../src/features/post-contract-actions/phases";
import { normalizeAction } from "../../src/features/question-cards/actionNormalization";
import { ContractDetailPage } from "../../src/pages/contract-detail/ContractDetailPage";
import { mvpService } from "../../src/services/mvpService";
import type { AnalysisRunDetailDto, AnalysisRunResultDto, GenerationResultDto } from "../../src/types/api";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ContractDetailPage", () => {
  it("combines generated text with saved state and shows histories", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    const originalTitle = document.title;
    const generation = generationResultFixture as GenerationResultDto;
    const action = generation.items[0].signing_checklist_items[0];
    const actionText = normalizeAction(action.text, "checklist").text;
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
    const completedDetails = completedSection.querySelector("details")!;
    const completedPostActionDetails = screen.getByRole("heading", { name: "완료된 계약 후 행동" }).closest("section")!.querySelector("details")!;
    expect(completedDetails).not.toHaveAttribute("open");
    expect(completedPostActionDetails).not.toHaveAttribute("open");
    fireEvent.click(completedDetails.querySelector("summary")!);
    expect(completedDetails).toHaveAttribute("open");
    expect(completedPostActionDetails).not.toHaveAttribute("open");
    expect(within(completedSection).getByText(actionText)).toBeInTheDocument();
    expect(within(completedSection).getByText(/근거 판정 R01/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "완료된 계약 후 행동" })).toBeInTheDocument();
    expect(screen.getByText("계약서 · contract.pdf")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /확인 결과 보기/ })).toHaveAttribute(
      "href",
      "/contracts/1001/report?analysisRunId=RUN-1001-001",
    );
    const printSheet = document.querySelector(".checklist-print-sheet");
    expect(printSheet).toHaveTextContent("확인 완료");
    expect(printSheet?.parentElement).toBe(document.body);
    fireEvent.click(screen.getByRole("button", { name: "체크리스트 PDF 저장" }));
    expect(print).toHaveBeenCalledOnce();
    expect(document.title).toBe(originalTitle);

    fireEvent.click(within(completedSection).getByRole("button", { name: `${actionText} 확인 취소` }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(1001, "checklist", action.item_key, false));
    const pendingSection = screen.getByRole("heading", { name: "서명 전 체크리스트" }).closest("section")!;
    expect(within(pendingSection).getByRole("button", { name: `${actionText} 확인` })).toBeInTheDocument();
  });

  it("shows only the first five pending items and hides the empty post-action column", async () => {
    const generation = generationResultFixture as GenerationResultDto;
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
    vi.spyOn(mvpService, "getDocuments").mockResolvedValue([]);
    vi.spyOn(mvpService, "getChecklist").mockResolvedValue([]);

    render(
      <MemoryRouter initialEntries={["/contracts/1001"]}>
        <Routes><Route path="/contracts/:contractId" element={<ContractDetailPage />} /></Routes>
      </MemoryRouter>,
    );

    const pendingSection = (await screen.findByRole("heading", { name: "서명 전 체크리스트" })).closest("section")!;
    expect(pendingSection.querySelectorAll(".check-item--row")).toHaveLength(5);
    const moreButton = within(pendingSection).getByRole("button", { name: /^남은 항목 \d+개 더 보기$/ });

    fireEvent.click(moreButton);

    expect(pendingSection.querySelectorAll(".check-item--row").length).toBeGreaterThan(5);
    expect(within(pendingSection).queryByRole("button", { name: /더 보기$/ })).not.toBeInTheDocument();
    expect(within(pendingSection).getByRole("progressbar", { name: /확인 완료/ })).toHaveAttribute("aria-valuenow", "0");
    // 남은 계약 후 행동이 없으면 빈 칸을 만들지 않는다.
    expect(screen.queryByRole("heading", { name: "계약 후 해야 할 행동" })).not.toBeInTheDocument();
  });

  it("moves a confirmed signing item below and reveals post-contract actions", async () => {
    const generation = structuredClone(generationResultFixture) as GenerationResultDto;
    const signingAction = generation.items[0].signing_checklist_items[0];
    const postAction = {
      item_key: "R01:post_action:000000000001",
      text: "전입신고와 확정일자를 완료한다.",
    };
    const normalizedPostActionText = normalizeAction(postAction.text, "post_action").text;
    const postActionText = standardPostActionFor(normalizedPostActionText)?.text
      ?? normalizedPostActionText;
    const signingActionText = normalizeAction(signingAction.text, "checklist").text;
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
    const activeGrid = (await screen.findByRole("heading", { name: "서명 전 체크리스트" })).closest(".checklist-active-grid")!;
    expect(within(activeGrid).getByRole("heading", { name: "계약 후 해야 할 행동" })).toBeInTheDocument();
    expect(within(activeGrid).getByText(postActionText)).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: `${signingActionText} 확인` }));

    await waitFor(() => expect(update).toHaveBeenCalledWith(1001, "checklist", signingAction.item_key, true));
    const completedSection = screen.getByRole("heading", { name: "완료된 체크리스트 항목" }).closest("section")!;
    fireEvent.click(completedSection.querySelector("summary")!);
    expect(within(completedSection).getByText(signingActionText)).toBeInTheDocument();
    const postActionSection = screen.getByRole("heading", { name: "계약 후 해야 할 행동" }).closest("section")!;
    expect(within(postActionSection).getByText(postActionText)).toBeInTheDocument();

    fireEvent.click(within(postActionSection).getByRole("button", { name: `${postActionText} 완료` }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(1001, "post_action", postAction.item_key, true));
    const completedPostActionSection = screen.getByRole("heading", { name: "완료된 계약 후 행동" }).closest("section")!;
    fireEvent.click(completedPostActionSection.querySelector("summary")!);
    expect(within(completedPostActionSection).getByText(postActionText)).toBeInTheDocument();
  });

  // 진행률 분모를 화면 제목 문자열로 고르면 제목을 바꿀 때 done이 조용히 0으로 굳는다.
  it("counts completed post-contract actions against the full total", async () => {
    const generation = structuredClone(generationResultFixture) as GenerationResultDto;
    for (const item of generation.items) item.post_contract_action_items = [];
    const doneAction = { item_key: "R01:post_action:000000000001", text: "전입신고와 확정일자를 완료한다." };
    const pendingAction = { item_key: "R01:post_action:000000000002", text: "임대차 신고를 접수한다." };
    generation.items[0].post_contract_action_items = [doneAction, pendingAction];
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
    vi.spyOn(mvpService, "getChecklist").mockResolvedValue([
      { kind: "post_action", item_key: doneAction.item_key, done: true, updated_at: "2026-07-18T01:00:00Z" },
    ]);

    render(
      <MemoryRouter initialEntries={["/contracts/1001"]}>
        <Routes><Route path="/contracts/:contractId" element={<ContractDetailPage />} /></Routes>
      </MemoryRouter>,
    );

    const postSection = (await screen.findByRole("heading", { name: "계약 후 해야 할 행동" })).closest("section")!;
    // 공식 보충 안내는 체크 진행률에 넣지 않는다.
    expect(within(postSection).getByText("1 / 2 확인 완료")).toBeInTheDocument();
    expect(within(postSection).getByRole("progressbar", { name: /확인 완료/ })).toHaveAttribute("aria-valuenow", "1");
    for (const phase of ["계약 체결 직후", "잔금 지급 전", "잔금 지급 시", "잔금·입주 후"]) {
      expect(screen.getAllByRole("heading", { name: phase }).length).toBeGreaterThan(0);
    }
    expect(screen.getByRole("heading", { name: "공식 안내에서 추가로 확인할 행동" })).toBeInTheDocument();
    expect(screen.getByText("도배·장판·수리 등 임대인이 약속한 특약이 이행됐는지 확인하세요.")).toBeInTheDocument();
    expect(within(postSection).getByText("계약 후 보증금과 임차인의 권리를 보호하기 위해 필요한 조치를 확인해 보세요.")).toBeInTheDocument();
    const signingSection = screen.getByRole("heading", { name: "서명 전 체크리스트" }).closest("section")!;
    expect(within(signingSection).getByText("서명하기 전, 금전 피해와 분쟁으로 이어질 수 있는 항목을 한 번 더 확인해 보세요.")).toBeInTheDocument();
    // 완료 섹션에는 안내 문구가 새어 나오지 않는다.
    const completedSection = screen.getByRole("heading", { name: "완료된 계약 후 행동" }).closest("section")!;
    expect(completedSection).not.toHaveTextContent("계약 후 보증금과 임차인의 권리를");
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
