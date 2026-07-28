// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ExtractionReviewPage } from "../../src/pages/extraction-review/ExtractionReviewPage";
import { mvpService } from "../../src/services/mvpService";
import type {
  AnalysisRunDetailDto,
  DocumentExtractionDto,
  ExtractedFieldDto,
  ExtractionStateDto,
  FieldValue,
} from "../../src/types/api";

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
    source_evidence: {
      page: value === null ? null : 1,
      text: value === null ? null : "문서 원문",
    },
    issue_code: value === null ? "unreadable" : null,
    failure_reason: null,
    ...options,
  };
}

function extractionWith(fields: Record<string, ExtractedFieldDto>): ExtractionStateDto {
  const contractDoc: DocumentExtractionDto = {
    schema_version: "1.9.0",
    document_id: "DOC-TEST",
    document_type: "contract",
    warnings: [],
    fields,
  };
  return {
    id: 19,
    status: "completed",
    error: null,
    contract_doc: contractDoc,
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

function mockContract(overrides: Record<string, unknown> = {}) {
  vi.spyOn(mvpService, "getContract").mockResolvedValue({
    id: 1001,
    title: "합성 계약",
    contract_type: null,
    contract_stage: null,
    deposit_paid: null,
    signed: null,
    move_in_date: null,
    balance_payment_date: null,
    is_proxy_contract: null,
    registry_case_id: null,
    action_status: "none",
    created_at: "2026-07-26T00:00:00Z",
    ...overrides,
  });
}

beforeEach(() => {
  mockContract();
  vi.spyOn(mvpService, "saveSituation").mockResolvedValue({} as never);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ExtractionReviewPage", () => {
  it("shows only unread fields with the simplified card", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      deposit: extractedField("deposit", 100000000),
      monthly_rent: extractedField("monthly_rent", null),
      landlord_name: extractedField("landlord_name", "권미래"),
    }));

    renderPage();

    expect(await screen.findByRole("heading", { name: "못 읽은 내용 확인" }))
      .toBeInTheDocument();
    expect(screen.getByText("문서에서 읽지 못한 항목을 원본 계약서와 비교해 입력해 주세요."))
      .toBeInTheDocument();
    expect(screen.getByText("월세 내용이 계약서와 같나요?")).toBeInTheDocument();
    expect(screen.getByText("글자를 읽지 못함")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "문서에서 읽은 내용" }))
      .toBeInTheDocument();
    expect(screen.getByText("읽은 내용이 없습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "직접 고칠게요" })).toBeInTheDocument();

    expect(screen.queryByRole("navigation", { name: "확인 묶음" })).not.toBeInTheDocument();
    expect(screen.queryByText("금전 피해로 이어질 수 있는 내용")).not.toBeInTheDocument();
    expect(screen.queryByText("책임과 특약")).not.toBeInTheDocument();
    expect(screen.queryByText("직접 알려주실 내용")).not.toBeInTheDocument();
    expect(screen.queryByText("나머지 내용")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "월세" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "문서에서 확인하기 어려워요" }))
      .not.toBeInTheDocument();
    expect(screen.queryByText("100,000,000")).not.toBeInTheDocument();
    expect(screen.queryByText("권미래")).not.toBeInTheDocument();
  });

  it("lets the user enter an unread value and keeps contract context separate", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      monthly_rent: extractedField("monthly_rent", null),
    }));

    renderPage();
    await screen.findByText("월세 내용이 계약서와 같나요?");

    const finish = screen.getByRole("button", { name: "남은 1개를 입력해 주세요" });
    expect(finish).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    fireEvent.change(await screen.findByRole("textbox", { name: "월세 수정 내용" }), {
      target: { value: "350000" },
    });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));

    expect(screen.getByRole("button", { name: "확인 완료" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "확인 완료" }));

    expect(screen.getByRole("heading", { name: "분석 준비를 마쳐 주세요" }))
      .toBeInTheDocument();
    expect(screen.getByRole("group", { name: "계약 유형만 선택해 주세요" }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "계약 상황을 입력해 주세요" }))
      .toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: "전세" }));
    expect(screen.queryByRole("group", { name: "계약 유형만 선택해 주세요" }))
      .not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }))
      .toBeEnabled();
  });

  it("marks every remaining unread field as unresolved with one button", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      monthly_rent: extractedField("monthly_rent", null),
      violation_building: extractedField("violation_building", null, {
        issue_code: null,
      }),
    }));

    renderPage();
    const confirmAll = await screen.findByRole("button", { name: "모두 확인하기" });
    fireEvent.click(confirmAll);

    expect(screen.getByRole("heading", { name: "분석 준비를 마쳐 주세요" }))
      .toBeInTheDocument();
    expect(screen.getByText(/확인하지 못한 항목/)).toHaveTextContent("2개");
    expect(screen.getByText("월세 · 문서에서 글자를 읽지 못함")).toBeInTheDocument();
    expect(screen.getByText("위반건축물 표시 · 다른 자료에서 직접 확인 필요"))
      .toBeInTheDocument();
  });

  it("continues when there are no unread fields", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      deposit: extractedField("deposit", 100000000),
    }));

    renderPage();

    expect(await screen.findByText("문서에서 못 읽은 내용이 없습니다."))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "확인 완료" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "확인 완료" }));
    expect(screen.getByRole("group", { name: "계약 유형만 선택해 주세요" }))
      .toBeInTheDocument();
  });

  it("saves the correction and contract situation before starting analysis", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      monthly_rent: extractedField("monthly_rent", null),
    }));
    const submit = vi.spyOn(mvpService, "submitCorrections").mockResolvedValue(extractionWith({}));
    const confirm = vi.spyOn(mvpService, "confirmExtraction").mockResolvedValue({
      input_snapshot_id: "SNAP-1001",
      created_at: "2026-07-16T00:00:00Z",
    });
    vi.spyOn(mvpService, "startAnalysis").mockResolvedValue(analysisRun());

    renderPage();
    await screen.findByText("월세 내용이 계약서와 같나요?");
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    fireEvent.change(await screen.findByRole("textbox", { name: "월세 수정 내용" }), {
      target: { value: "350000" },
    });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));
    fireEvent.click(screen.getByRole("button", { name: "확인 완료" }));
    fireEvent.click(screen.getByRole("radio", { name: "전세" }));
    fireEvent.click(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }));

    await waitFor(() => expect(screen.getByText(/분석 화면/)).toBeInTheDocument());
    expect(mvpService.saveSituation).toHaveBeenCalledWith(1001, expect.objectContaining({
      contract_type: "전세",
    }));
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({
      contract_id: 1001,
      corrections: [
        expect.objectContaining({
          field_name: "monthly_rent",
          corrected_value: 350000,
        }),
      ],
    }));
    expect(confirm).toHaveBeenCalledWith(1001, expect.objectContaining({
      unresolved_fields: [],
    }));
    expect(screen.getByText(/analysisRunId=RUN-1001-001/)).toBeInTheDocument();
  });

  it("shows extraction failures and empty results", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValueOnce({
      id: 2,
      status: "failed",
      error: "OCR 실패",
      contract_doc: null,
      registry_doc: null,
      created_at: "2026-07-18T00:00:00Z",
    });

    const first = renderPage();
    expect(await screen.findByText("OCR 실패")).toBeInTheDocument();
    first.unmount();
    vi.restoreAllMocks();

    mockContract();
    vi.spyOn(mvpService, "saveSituation").mockResolvedValue({} as never);
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue({
      id: 3,
      status: "completed",
      error: null,
      contract_doc: null,
      registry_doc: null,
      created_at: "2026-07-18T00:00:00Z",
    });
    renderPage();
    expect(await screen.findByText("확인할 문서 내용이 없습니다")).toBeInTheDocument();
  });

  it("restores an already saved contract situation", async () => {
    vi.restoreAllMocks();
    mockContract({
      contract_type: "보증부 월세",
      contract_stage: "서명 전",
      deposit_paid: true,
      signed: false,
    });
    vi.spyOn(mvpService, "saveSituation").mockResolvedValue({} as never);
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(extractionWith({
      deposit: extractedField("deposit", 100000000),
    }));

    renderPage();
    await screen.findByText("문서에서 못 읽은 내용이 없습니다.");
    fireEvent.click(screen.getByRole("button", { name: "확인 완료" }));

    expect(screen.queryByRole("group", { name: "계약 유형만 선택해 주세요" }))
      .not.toBeInTheDocument();
    expect(screen.queryByText("계약 상황 알려주기")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }))
      .toBeEnabled();
  });
});
