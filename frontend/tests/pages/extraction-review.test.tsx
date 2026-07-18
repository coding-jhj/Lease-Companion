// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import contractExtractionFixture from "../../../data/sample/fixtures/case-001/contract_extraction.json";
import registryExtractionFixture from "../../../data/sample/fixtures/case-001/registry_extraction.json";
import correctionRequestFixture from "../../../data/sample/fixtures/case-001/correction_request.json";
import { ExtractionReviewPage } from "../../src/pages/extraction-review/ExtractionReviewPage";
import { mvpService } from "../../src/services/mvpService";
import type { DocumentExtractionDto, ExtractionStateDto } from "../../src/types/api";

const documents = [
  contractExtractionFixture as DocumentExtractionDto,
  registryExtractionFixture as DocumentExtractionDto,
];

const completedExtraction: ExtractionStateDto = {
  id: 1,
  status: "completed",
  error: null,
  contract_doc: documents[0],
  registry_doc: documents[1],
  created_at: "2026-07-16T00:00:00Z",
};

const emptyExtraction: ExtractionStateDto = {
  ...completedExtraction,
  contract_doc: null,
  registry_doc: null,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/contracts/1001/review"]}>
      <Routes>
        <Route path="/contracts/:contractId/review" element={<ExtractionReviewPage />} />
        <Route path="/contracts/:contractId/analyzing" element={<p>분석 화면</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ExtractionReviewPage", () => {
  it("shows canonical states and sends only changed fields before confirmation", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(completedExtraction);
    const submit = vi.spyOn(mvpService, "submitCorrections").mockResolvedValue(
      completedExtraction,
    );
    const confirm = vi.spyOn(mvpService, "confirmExtraction").mockResolvedValue(
      { input_snapshot_id: "SNAP-1001", created_at: "2026-07-16T00:00:00Z" },
    );

    renderPage();

    expect(screen.getByText("추출 상태를 확인하는 중")).toBeInTheDocument();
    expect(await screen.findByLabelText("입금 계좌 예금주 값")).toHaveValue("");
    expect(screen.getAllByText("추출됨").length).toBeGreaterThan(0);
    expect(screen.getByText("불확실")).toBeInTheDocument();
    expect(screen.getAllByText("실패").length).toBeGreaterThan(0);
    expect(screen.getAllByText("미확인").length).toBe(documents.flatMap((item) => Object.values(item.fields)).length);
    expect(screen.getAllByText("원문 위치 미확인").length).toBeGreaterThan(0);
    expect(screen.getByText("입금 계좌 예금주 칸을 문서에서 읽지 못했습니다.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "읽힌 값 모두 확인" }));
    fireEvent.change(screen.getByLabelText("입금 계좌 예금주 값"), {
      target: { value: "이정훈" },
    });

    expect(screen.getAllByText("확인됨").length).toBeGreaterThan(0);
    expect(screen.getByText("수정됨")).toBeInTheDocument();
    expect(screen.getByText("저장되지 않은 수정 1건")).toBeInTheDocument();
    const analyzeButton = screen.getByRole("button", { name: "확인 완료하고 분석하기" });
    expect(analyzeButton).toBeEnabled();
    fireEvent.click(analyzeButton);

    await waitFor(() => {
      expect(submit).toHaveBeenCalledWith(correctionRequestFixture);
      expect(confirm).toHaveBeenCalledWith(1001);
    });
    expect(await screen.findByText("분석 화면")).toBeInTheDocument();
  });

  it("renders load error, retry, and empty states", async () => {
    vi.spyOn(mvpService, "getLatestExtraction")
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce(emptyExtraction);

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("network down");
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(await screen.findByText("확인할 추출값이 없습니다")).toBeInTheDocument();
  });

  it("blocks analysis while unverified fields remain", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(completedExtraction);
    renderPage();

    const analyzeButton = await screen.findByRole("button", { name: "확인 완료하고 분석하기" });
    expect(analyzeButton).toBeDisabled();
    expect(screen.getByText("미확인 필드가 남아 있어 분석을 시작할 수 없습니다.")).toBeInTheDocument();
  });

  it("keeps correction and confirmation failures separate and retryable", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(completedExtraction);
    vi.spyOn(mvpService, "submitCorrections")
      .mockRejectedValueOnce(new Error("correction down"))
      .mockResolvedValueOnce(completedExtraction);
    vi.spyOn(mvpService, "confirmExtraction").mockRejectedValue(
      new Error("confirmation down"),
    );
    renderPage();

    await screen.findByLabelText("입금 계좌 예금주 값");
    fireEvent.click(screen.getByRole("button", { name: "읽힌 값 모두 확인" }));
    fireEvent.change(screen.getByLabelText("입금 계좌 예금주 값"), {
      target: { value: "이정훈" },
    });

    fireEvent.click(screen.getByRole("button", { name: "확인 완료하고 분석하기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "수정 요청 실패: correction down",
    );

    fireEvent.click(screen.getByRole("button", { name: "확인 완료하고 분석하기" }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "확인 실패: confirmation down",
      );
    });
    expect(screen.getByRole("button", { name: "확인 완료하고 분석하기" })).toBeEnabled();
  });
});
