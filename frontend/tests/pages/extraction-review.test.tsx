// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import contractExtractionFixture from "../../../data/sample/fixtures/case-001/contract_extraction.json";
import registryExtractionFixture from "../../../data/sample/fixtures/case-001/registry_extraction.json";
import { ExtractionReviewPage } from "../../src/pages/extraction-review/ExtractionReviewPage";
import { mvpService } from "../../src/services/mvpService";
import type {
  AnalysisRunDetailDto,
  DocumentExtractionDto,
  ExtractedFieldDto,
  ExtractionStateDto,
  FieldValue,
  SchemaVersion,
} from "../../src/types/api";

const fixtureDocuments = [
  contractExtractionFixture as DocumentExtractionDto,
  registryExtractionFixture as DocumentExtractionDto,
];

const completedExtraction: ExtractionStateDto = {
  id: 1,
  status: "completed",
  error: null,
  contract_doc: fixtureDocuments[0],
  registry_doc: fixtureDocuments[1],
  created_at: "2026-07-16T00:00:00Z",
};

const emptyExtraction: ExtractionStateDto = {
  ...completedExtraction,
  contract_doc: null,
  registry_doc: null,
};

function extractedField(
  fieldName: string,
  value: FieldValue,
  options: Partial<ExtractedFieldDto> = {},
): ExtractedFieldDto {
  return {
    field_name: fieldName,
    extracted_value: value,
    normalized_value: value,
    user_corrected_value: null,
    verification_status: "unverified",
    confidence: value === null ? "실패" : "추출됨",
    source_evidence: { page: value === null ? null : 1, text: value === null ? null : "문서 원문" },
    issue_code: value === null ? "unreadable" : null,
    failure_reason: null,
    ...options,
  };
}

function extractionWith(
  fields: Record<string, ExtractedFieldDto>,
  schemaVersion: SchemaVersion = "1.9.0",
): ExtractionStateDto {
  return {
    id: 19,
    status: "completed",
    error: null,
    contract_doc: {
      schema_version: schemaVersion,
      document_id: "DOC-TEST",
      document_type: "contract",
      warnings: [],
      fields,
    },
    registry_doc: null,
    created_at: "2026-07-18T00:00:00Z",
  };
}

function analysisRun(): AnalysisRunDetailDto {
  return {
    analysis_run_id: "RUN-1001-001",
    input_snapshot_id: "SNAP-1001",
    status: "pending",
    error: null,
    created_at: "2026-07-16T00:00:00Z",
    result: null,
    generation_result: null,
    generation_status: null,
    generation_error: null,
  };
}

function AnalysisDestination() {
  const location = useLocation();
  return <p>분석 화면 {location.search}</p>;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/contracts/1001/review"]}>
      <Routes>
        <Route path="/contracts/:contractId/review" element={<ExtractionReviewPage />} />
        <Route path="/contracts/:contractId/analyzing" element={<AnalysisDestination />} />
        <Route path="/contracts/:contractId/upload" element={<p>문서 업로드 화면</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

function finishRemainingQueue() {
  for (let guard = 0; guard < 100; guard += 1) {
    const confirmButton = screen.queryByRole("button", { name: "네, 맞아요" });
    if (!confirmButton) return;
    fireEvent.click(confirmButton);
  }
  throw new Error("review queue did not finish");
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("ExtractionReviewPage", () => {
  it("guides the user through one important item at a time without technical labels", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(completedExtraction);

    const view = renderPage();

    expect(await screen.findByText(/중요한 내용 .*개 중 .*개를 확인했습니다/))
      .toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /주소/ })).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));
    expect(await screen.findByRole("heading", { name: "등기사항증명서 계약하려는 집 주소" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));
    expect(await screen.findByRole("heading", { name: /임대인/ })).toBeInTheDocument();
    expect(view.container.textContent).not.toMatch(/추출값|필드|confidence|스냅샷/);
  });

  it("keeps one guided card and requires both contract and registry values", async () => {
    const extraction = extractionWith({
      property_address: extractedField("property_address", "계약서 주소"),
    });
    extraction.registry_doc = {
      schema_version: "1.9.0",
      document_id: "REG-TEST",
      document_type: "registry",
      warnings: [],
      fields: {
        property_address: extractedField("property_address", "등기 주소", {
          confidence: "불확실",
        }),
      },
    };
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extraction);

    renderPage();

    await screen.findByRole("heading", { name: "계약서 계약하려는 집 주소" });
    expect(screen.getAllByRole("article")).toHaveLength(1);
    const disclosure = screen.getByText("문서에서 읽은 전체 내용 보기").closest("details");
    expect(disclosure).not.toBeNull();
    expect(within(disclosure!).getByText("계약서 주소")).toBeInTheDocument();
    expect(within(disclosure!).getByText("등기 주소")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));
    expect(await screen.findByRole("heading", { name: "등기사항증명서 계약하려는 집 주소" })).toBeInTheDocument();
  });

  it("keeps edits and unresolved reasons when moving backward and shows the completion summary", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      property_address: extractedField("property_address", "기존 주소"),
      landlord_name: extractedField("landlord_name", "이정훈"),
    }));

    renderPage();

    await screen.findByRole("heading", { name: "계약하려는 집 주소" });
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    fireEvent.change(await screen.findByRole("textbox", { name: /주소 수정 내용/ }), {
      target: { value: "수정 주소" },
    });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));
    expect(screen.getByRole("heading", { name: "임대인 이름" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "이전 내용 보기" }));
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    expect(screen.getByRole("textbox", { name: /주소 수정 내용/ })).toHaveValue("수정 주소");
    fireEvent.click(screen.getByRole("button", { name: "수정 취소" }));
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));

    fireEvent.click(screen.getByRole("button", { name: "문서에서 확인하기 어려워요" }));
    fireEvent.click(screen.getByLabelText("어디를 봐야 할지 모르겠어요"));

    expect(screen.getByRole("heading", { name: "중요한 내용을 모두 확인했습니다" }))
      .toBeInTheDocument();
    expect(screen.getByText(/확인한 항목/)).toHaveTextContent("1개");
    expect(screen.getByText(/확인하지 못한 항목/)).toHaveTextContent("1개");
    expect(screen.getByText(/확인하지 못한 내용도 결과에서 물어볼 항목으로 안내합니다/))
      .toBeInTheDocument();
    expect(screen.getByText("임대인 이름 · 확인할 위치를 찾기 어려움")).toBeInTheDocument();

    fireEvent.click(screen.getByText("문서에서 읽은 전체 내용 보기"));
    expect(screen.getByRole("heading", { name: "계약 당사자·목적물" })).toBeInTheDocument();
  });

  it("sends only changed fields, then confirms, starts analysis, and navigates with the run id", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      property_address: extractedField("property_address", "기존 주소"),
      landlord_name: extractedField("landlord_name", "이정훈"),
    }));
    const callOrder: string[] = [];
    const submit = vi.spyOn(mvpService, "submitCorrections").mockImplementation(async () => {
      callOrder.push("correction");
      return extractionWith({});
    });
    const confirm = vi.spyOn(mvpService, "confirmExtraction").mockImplementation(async () => {
      callOrder.push("confirm");
      return { input_snapshot_id: "SNAP-1001", created_at: "2026-07-16T00:00:00Z" };
    });
    const start = vi.spyOn(mvpService, "startAnalysis").mockImplementation(async () => {
      callOrder.push("analysis");
      return analysisRun();
    });

    renderPage();

    await screen.findByRole("heading", { name: "계약하려는 집 주소" });
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    fireEvent.change(await screen.findByRole("textbox", { name: /주소 수정 내용/ }), {
      target: { value: "수정 주소" },
    });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));
    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));

    await waitFor(() => {
      expect(submit).toHaveBeenCalledWith({
        schema_version: "1.9.0",
        contract_id: 1001,
        corrections: [{
          document_type: "contract",
          field_name: "property_address",
          corrected_value: "수정 주소",
        }],
      });
      expect(confirm).toHaveBeenCalledWith(1001);
      expect(start).toHaveBeenCalledWith(1001);
    });
    expect(callOrder).toEqual(["correction", "confirm", "analysis"]);
    expect(await screen.findByText(/분석 화면 \?analysisRunId=RUN-1001-001/))
      .toBeInTheDocument();
  });

  it("recovers a lost analysis POST response from a run with the confirmed snapshot", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      property_address: extractedField("property_address", "기존 주소"),
    }));
    vi.spyOn(mvpService, "confirmExtraction").mockResolvedValue({
      input_snapshot_id: "SNAP-RECOVER", created_at: "2026-07-23T00:00:00Z",
    });
    const start = vi.spyOn(mvpService, "startAnalysis").mockRejectedValue(new Error("response lost"));
    const list = vi.spyOn(mvpService, "getAnalysisRuns").mockResolvedValue([{
      analysis_run_id: "RUN-RECOVER", input_snapshot_id: "SNAP-RECOVER", status: "pending", created_at: "2026-07-23T00:00:00Z",
    }]);

    renderPage();

    await screen.findByRole("heading", { name: "계약하려는 집 주소" });
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));
    fireEvent.click(await screen.findByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));

    await waitFor(() => expect(list).toHaveBeenCalledWith(1001));
    expect(start).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/분석 화면 \?analysisRunId=RUN-RECOVER/)).toBeInTheDocument();
  });

  it("recovers an uncertain analysis start before retrying POST when the run appears", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      property_address: extractedField("property_address", "기존 주소"),
    }));
    vi.spyOn(mvpService, "confirmExtraction").mockResolvedValue({
      input_snapshot_id: "SNAP-UNCERTAIN", created_at: "2026-07-24T00:00:00Z",
    });
    const start = vi.spyOn(mvpService, "startAnalysis")
      .mockRejectedValueOnce(new Error("response lost"))
      .mockResolvedValueOnce(analysisRun());
    const list = vi.spyOn(mvpService, "getAnalysisRuns")
      .mockRejectedValueOnce(new Error("recovery unavailable"))
      .mockResolvedValueOnce([{
        analysis_run_id: "RUN-RECOVERED", input_snapshot_id: "SNAP-UNCERTAIN", status: "pending", created_at: "2026-07-24T00:00:00Z",
      }]);

    renderPage();

    await screen.findByRole("heading", { name: "계약하려는 집 주소" });
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));
    fireEvent.click(await screen.findByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("확인 결과 준비를 시작하지 못했습니다");
    expect(start).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));

    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
    expect(start).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/분석 화면 \?analysisRunId=RUN-RECOVERED/)).toBeInTheDocument();
  });

  it("keeps an uncertain analysis start retryable without another POST when recovery still fails", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      property_address: extractedField("property_address", "기존 주소"),
    }));
    vi.spyOn(mvpService, "confirmExtraction").mockResolvedValue({
      input_snapshot_id: "SNAP-UNCERTAIN", created_at: "2026-07-24T00:00:00Z",
    });
    const start = vi.spyOn(mvpService, "startAnalysis")
      .mockRejectedValueOnce(new Error("response lost"))
      .mockResolvedValueOnce(analysisRun());
    const list = vi.spyOn(mvpService, "getAnalysisRuns")
      .mockRejectedValueOnce(new Error("first recovery unavailable"))
      .mockRejectedValueOnce(new Error("retry recovery unavailable"));

    renderPage();

    await screen.findByRole("heading", { name: "계약하려는 집 주소" });
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));
    fireEvent.click(await screen.findByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("확인 결과 준비를 시작하지 못했습니다");

    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));

    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
    expect(start).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("alert")).toHaveTextContent("확인 결과 준비를 시작하지 못했습니다");
  });

  it("starts a new analysis only after an uncertain retry confirms no matching run", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      property_address: extractedField("property_address", "기존 주소"),
    }));
    vi.spyOn(mvpService, "confirmExtraction").mockResolvedValue({
      input_snapshot_id: "SNAP-UNCERTAIN", created_at: "2026-07-24T00:00:00Z",
    });
    const start = vi.spyOn(mvpService, "startAnalysis")
      .mockRejectedValueOnce(new Error("response lost"))
      .mockResolvedValueOnce(analysisRun());
    const list = vi.spyOn(mvpService, "getAnalysisRuns")
      .mockRejectedValueOnce(new Error("first recovery unavailable"))
      .mockResolvedValueOnce([]);

    renderPage();

    await screen.findByRole("heading", { name: "계약하려는 집 주소" });
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));
    fireEvent.click(await screen.findByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("확인 결과 준비를 시작하지 못했습니다");

    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));

    expect(await screen.findByText(/분석 화면 \?analysisRunId=RUN-1001-001/)).toBeInTheDocument();
    expect(list).toHaveBeenCalledTimes(2);
    expect(start).toHaveBeenCalledTimes(2);
  });

  it("submits special clauses as a newline-derived array", async () => {
    const extraction = extractionWith({
      special_clauses: extractedField("special_clauses", ["첫 특약"]),
    });
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extraction);
    const submit = vi.spyOn(mvpService, "submitCorrections").mockResolvedValue(extraction);
    vi.spyOn(mvpService, "confirmExtraction").mockResolvedValue(
      { input_snapshot_id: "SNAP-19", created_at: "2026-07-18T00:00:00Z" },
    );
    vi.spyOn(mvpService, "startAnalysis").mockResolvedValue(analysisRun());

    renderPage();

    await screen.findByRole("heading", { name: "특약 내용" });
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    fireEvent.change(screen.getByRole("textbox", { name: "특약사항 수정 내용" }), {
      target: { value: "첫 특약\n둘째 특약은 쉼표, 그대로" },
    });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));
    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith({
      schema_version: "1.9.0",
      contract_id: 1001,
      corrections: [{
        document_type: "contract",
        field_name: "special_clauses",
        corrected_value: ["첫 특약", "둘째 특약은 쉼표, 그대로"],
      }],
    }));
  });

  it("keeps the corrected draft and completion screen after correction failure, then retries", async () => {
    const extraction = extractionWith({
      property_address: extractedField("property_address", "기존 주소"),
    });
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extraction);
    const submit = vi.spyOn(mvpService, "submitCorrections")
      .mockRejectedValueOnce(new Error("correction down"))
      .mockResolvedValueOnce(extraction);
    const confirm = vi.spyOn(mvpService, "confirmExtraction").mockResolvedValue(
      { input_snapshot_id: "SNAP-1001", created_at: "2026-07-16T00:00:00Z" },
    );
    vi.spyOn(mvpService, "startAnalysis").mockResolvedValue(analysisRun());

    renderPage();

    await screen.findByRole("heading", { name: "계약하려는 집 주소" });
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    fireEvent.change(screen.getByRole("textbox", { name: /주소 수정 내용/ }), {
      target: { value: "수정 주소" },
    });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));
    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "수정한 내용을 저장하지 못했습니다. 입력한 내용은 이 화면에 남아 있습니다.",
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("correction down");
    expect(screen.getByRole("heading", { name: "중요한 내용을 모두 확인했습니다" }))
      .toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "이전 내용 보기" }));
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    expect(screen.getByRole("textbox", { name: /주소 수정 내용/ })).toHaveValue("수정 주소");
    fireEvent.click(screen.getByRole("button", { name: "수정 취소" }));
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));
    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));

    await waitFor(() => expect(submit).toHaveBeenCalledTimes(2));
    expect(confirm).toHaveBeenCalledTimes(1);
  });

  it("keeps confirmation and analysis failures separate and retryable", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      property_address: extractedField("property_address", "기존 주소"),
    }));
    const confirm = vi.spyOn(mvpService, "confirmExtraction")
      .mockRejectedValueOnce(new Error("confirmation down"))
      .mockResolvedValueOnce(
        { input_snapshot_id: "SNAP-1001", created_at: "2026-07-16T00:00:00Z" },
      );
    const start = vi.spyOn(mvpService, "startAnalysis")
      .mockRejectedValueOnce(new Error("analysis down"))
      .mockResolvedValueOnce(analysisRun());
    vi.spyOn(mvpService, "getAnalysisRuns").mockResolvedValue([]);

    renderPage();
    await screen.findByRole("heading", { name: "계약하려는 집 주소" });
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));

    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "문서 내용 확인을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("confirmation down");
    expect(start).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "확인 결과 준비를 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("analysis down");
    expect(confirm).toHaveBeenCalledTimes(2);

    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));
    await waitFor(() => expect(start).toHaveBeenCalledTimes(2));
    expect(confirm).toHaveBeenCalledTimes(2);
  });

  it("reconfirms after a saved correction is restored to the original value", async () => {
    const extraction = extractionWith({
      property_address: extractedField("property_address", "기존 주소"),
    });
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extraction);
    const callOrder: string[] = [];
    const submit = vi.spyOn(mvpService, "submitCorrections").mockImplementation(async () => {
      callOrder.push("correction");
      return extraction;
    });
    const confirm = vi.spyOn(mvpService, "confirmExtraction").mockImplementation(async () => {
      callOrder.push("confirm");
      return { input_snapshot_id: "SNAP-1001", created_at: "2026-07-16T00:00:00Z" };
    });
    const start = vi.spyOn(mvpService, "startAnalysis")
      .mockImplementationOnce(async () => {
        callOrder.push("analysis");
        throw new Error("analysis down");
      })
      .mockImplementationOnce(async () => {
        callOrder.push("analysis");
        return analysisRun();
      });

    renderPage();
    await screen.findByRole("heading", { name: "계약하려는 집 주소" });
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    fireEvent.change(screen.getByRole("textbox", { name: /주소 수정 내용/ }), {
      target: { value: "첫 수정 주소" },
    });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));
    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "확인 결과 준비를 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    );

    fireEvent.click(screen.getByRole("button", { name: "이전 내용 보기" }));
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    fireEvent.change(screen.getByRole("textbox", { name: /주소 수정 내용/ }), {
      target: { value: "기존 주소" },
    });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));
    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));

    await waitFor(() => expect(start).toHaveBeenCalledTimes(2));
    expect(submit).toHaveBeenCalledTimes(2);
    expect(submit).toHaveBeenLastCalledWith({
      schema_version: "1.9.0",
      contract_id: 1001,
      corrections: [{
        document_type: "contract",
        field_name: "property_address",
        corrected_value: "기존 주소",
      }],
    });
    expect(confirm).toHaveBeenCalledTimes(2);
    expect(callOrder).toEqual([
      "correction",
      "confirm",
      "analysis",
      "correction",
      "confirm",
      "analysis",
    ]);
  });

  it("allows unresolved items to reach analysis without sending their reasons to the backend", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      property_address: extractedField("property_address", "기존 주소"),
    }));
    const submit = vi.spyOn(mvpService, "submitCorrections");
    vi.spyOn(mvpService, "confirmExtraction").mockResolvedValue(
      { input_snapshot_id: "SNAP-1001", created_at: "2026-07-16T00:00:00Z" },
    );
    const start = vi.spyOn(mvpService, "startAnalysis").mockResolvedValue(analysisRun());

    renderPage();
    await screen.findByRole("heading", { name: "계약하려는 집 주소" });
    fireEvent.click(screen.getByRole("button", { name: "문서에서 확인하기 어려워요" }));
    fireEvent.click(screen.getByLabelText("문서에 적혀 있지 않아요"));
    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));

    await waitFor(() => expect(start).toHaveBeenCalledWith(1001));
    expect(submit).not.toHaveBeenCalled();
  });

  it("polls pending extraction to completion", async () => {
    vi.useFakeTimers();
    const pending: ExtractionStateDto = {
      ...emptyExtraction,
      status: "pending",
    };
    vi.spyOn(mvpService, "getLatestExtraction")
      .mockResolvedValueOnce(pending)
      .mockResolvedValueOnce(extractionWith({
        property_address: extractedField("property_address", "기존 주소"),
      }));

    renderPage();

    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText("문서 읽기 대기 중")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });
    expect(screen.getByRole("heading", { name: "계약하려는 집 주소" })).toBeInTheDocument();
  });

  it("shows extraction failures and empty results", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValueOnce({
      ...emptyExtraction,
      status: "failed",
      error: "문서 형식을 읽지 못했습니다.",
    });
    const first = renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("문서 형식을 읽지 못했습니다.");
    first.unmount();

    vi.restoreAllMocks();
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(emptyExtraction);
    renderPage();
    expect(await screen.findByText("확인할 문서 내용이 없습니다")).toBeInTheDocument();
  });

  it("shows polling timeout and aborts an active poll on unmount", async () => {
    vi.useFakeTimers();
    const pending: ExtractionStateDto = {
      ...emptyExtraction,
      status: "pending",
    };
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(pending);
    const first = renderPage();

    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText("문서 읽기 대기 중")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "처리가 예상보다 오래 걸리고 있습니다.",
    );
    first.unmount();

    vi.useRealTimers();
    vi.restoreAllMocks();
    const pendingAgain = vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(pending);
    const second = renderPage();
    await screen.findByText("문서 읽기 대기 중");
    const signal = pendingAgain.mock.calls[0]?.[1];
    expect(signal?.aborted).toBe(false);
    second.unmount();
    expect(signal?.aborted).toBe(true);
  });

  it("returns to upload when extraction loading rejects", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockRejectedValue(new Error("network down"));

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("network down");
    fireEvent.click(screen.getByRole("button", { name: "문서 다시 올리기" }));
    expect(await screen.findByText("문서 업로드 화면")).toBeInTheDocument();
  });

  it("starts on the first unverified item while preserving already reviewed progress", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      property_address: extractedField("property_address", "기존 주소", {
        verification_status: "confirmed",
      }),
      landlord_name: extractedField("landlord_name", "이정훈"),
    }));

    renderPage();

    expect(await screen.findByText("중요한 내용 2개 중 1개를 확인했습니다."))
      .toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "임대인 이름" })).toBeInTheDocument();
  });

  it("skips already reviewed items while advancing the queue", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      property_address: extractedField("property_address", "기존 주소"),
      landlord_name: extractedField("landlord_name", "이정훈", {
        verification_status: "confirmed",
      }),
      deposit: extractedField("deposit", 300_000_000),
    }));

    renderPage();

    await screen.findByRole("heading", { name: "계약하려는 집 주소" });
    fireEvent.click(screen.getByRole("button", { name: "네, 맞아요" }));
    expect(screen.getByRole("heading", { name: "보증금" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "임대인 이름" })).not.toBeInTheDocument();
  });
});
