// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import contractExtractionFixture from "../../../data/sample/fixtures/case-001/contract_extraction.json";
import registryExtractionFixture from "../../../data/sample/fixtures/case-001/registry_extraction.json";
import correctionRequestFixture from "../../../data/sample/fixtures/case-001/correction_request.json";
import { fieldViewModels } from "../../src/features/extraction-review/viewModel";
import { ExtractionReviewPage } from "../../src/pages/extraction-review/ExtractionReviewPage";
import { mvpService } from "../../src/services/mvpService";
import type { DocumentExtractionDto, ExtractedFieldDto, ExtractionStateDto, FieldValue } from "../../src/types/api";

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
        <Route path="/contracts/:contractId/upload" element={<p>문서 업로드 화면</p>} />
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
    expect(screen.getAllByText("판독 실패").length).toBeGreaterThan(0);
    expect(screen.getAllByText("판독 실패 해결 방법").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/직접 입력한 값은 자동 추출값이 아니라/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("미확인").length).toBe(fieldViewModels(documents).length);
    expect(screen.queryByText("원문 위치 미확인")).not.toBeInTheDocument();
    expect(screen.getByText("입금 계좌 예금주 칸을 문서에서 읽지 못했습니다.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "이번 단계에서 확인할 내용" })).toBeInTheDocument();
    expect(screen.getByText("표준계약서 서식")).toBeInTheDocument();
    expect(screen.getByText("특약 원문")).toBeInTheDocument();
    expect(screen.getByText("금전피해 관련 핵심값")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /특약·핵심값 확인/ })).toBeInTheDocument();
    expect(screen.getByText("문서에서 읽힌 값").closest("details")).not.toHaveAttribute("open");
    expect(screen.getByText("그 밖에 읽지 못한 값").closest("details")).not.toHaveAttribute("open");

    fireEvent.click(screen.getByRole("button", { name: "읽힌 값 모두 확인" }));
    fireEvent.click(screen.getByRole("button", { name: "특약사항 이 값 확인" }));
    const confirmedSummary = screen.getByText(/확인된 항목 \d+개/);
    expect(confirmedSummary.closest("details")).not.toHaveAttribute("open");
    fireEvent.change(screen.getByLabelText("입금 계좌 예금주 값"), {
      target: { value: "이정훈" },
    });

    expect(screen.getAllByText("확인됨").length).toBeGreaterThan(0);
    expect(screen.getByText("수정됨")).toBeInTheDocument();
    expect(screen.getByText("저장되지 않은 수정 1건")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "입금 계좌 예금주 이 값 확인" }));
    const analyzeButton = screen.getByRole("button", { name: "확인 완료하고 분석하기" });
    expect(analyzeButton).toBeEnabled();
    fireEvent.click(analyzeButton);

    await waitFor(() => {
      expect(submit).toHaveBeenCalledWith(correctionRequestFixture);
      expect(confirm).toHaveBeenCalledWith(1001);
    });
    expect(await screen.findByText("분석 화면")).toBeInTheDocument();
  });

  it("submits v1.9 clause arrays item by item without comma splitting", async () => {
    function field(field_name: string, extracted_value: FieldValue): ExtractedFieldDto {
      return {
        field_name,
        extracted_value,
        normalized_value: null,
        user_corrected_value: null,
        verification_status: "confirmed",
        confidence: extracted_value === null ? "실패" : "추출됨",
        source_evidence: { page: 2, text: "조항 원문" },
        issue_code: extracted_value === null ? "unreadable" : null,
        failure_reason: null,
      };
    }

    const contract: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-19",
      document_type: "contract",
      warnings: [],
      fields: {
        deposit_return_condition: field("deposit_return_condition", null),
        repair_responsibility: field("repair_responsibility", null),
        deposit_return_clause: field("deposit_return_clause", "계약 종료일에 반환한다."),
        repair_responsibility_clause: field("repair_responsibility_clause", "임대인이 수리한다."),
        main_clauses: field("main_clauses", ["첫 조항", "둘째 조항"]),
        special_clauses: field("special_clauses", ["첫 특약"]),
      },
    };
    const v19Extraction: ExtractionStateDto = {
      id: 19,
      status: "completed",
      error: null,
      contract_doc: contract,
      registry_doc: null,
      created_at: "2026-07-18T00:00:00Z",
    };
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(v19Extraction);
    const submit = vi.spyOn(mvpService, "submitCorrections").mockResolvedValue(v19Extraction);
    vi.spyOn(mvpService, "confirmExtraction").mockResolvedValue(
      { input_snapshot_id: "SNAP-19", created_at: "2026-07-18T00:00:00Z" },
    );

    renderPage();

    expect(await screen.findByLabelText("계약서 본문 주요 조항 2 값")).toHaveValue("둘째 조항");
    expect(screen.queryByLabelText("보증금 반환 조건 값")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("수리·원상복구 책임 값")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("계약서 본문 주요 조항 2 값"), {
      target: { value: "둘째 조항은 유지하고, 쉼표도 보존한다." },
    });
    fireEvent.click(screen.getByRole("button", { name: "계약서 본문 주요 조항 이 값 확인" }));
    fireEvent.click(screen.getByRole("button", { name: "확인 완료하고 분석하기" }));

    await waitFor(() => {
      expect(submit).toHaveBeenCalledWith({
        schema_version: "1.9.0",
        contract_id: 1001,
        corrections: [{
          document_type: "contract",
          field_name: "main_clauses",
          corrected_value: ["첫 조항", "둘째 조항은 유지하고, 쉼표도 보존한다."],
        }],
      });
    });
  });

  it("requires choice-based guarantee and sublease authority confirmations", async () => {
    const failedField = (field_name: string): ExtractedFieldDto => ({
      field_name,
      extracted_value: null,
      normalized_value: null,
      user_corrected_value: null,
      verification_status: "unverified",
      confidence: "실패",
      source_evidence: { page: null, text: null },
      issue_code: "not_stated",
      failure_reason: "사용자가 직접 확인하는 항목입니다.",
    });
    const contract: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-CHOICES",
      document_type: "contract",
      warnings: [],
      fields: {
        guarantee_eligibility_confirmed: failedField("guarantee_eligibility_confirmed"),
        lessor_sublease_authority_confirmed: failedField("lessor_sublease_authority_confirmed"),
      },
    };
    const choiceExtraction: ExtractionStateDto = {
      id: 20,
      status: "completed",
      error: null,
      contract_doc: contract,
      registry_doc: null,
      created_at: "2026-07-21T00:00:00Z",
    };
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(choiceExtraction);
    const submit = vi.spyOn(mvpService, "submitCorrections").mockResolvedValue(choiceExtraction);
    vi.spyOn(mvpService, "confirmExtraction").mockResolvedValue(
      { input_snapshot_id: "SNAP-CHOICES", created_at: "2026-07-21T00:00:00Z" },
    );

    renderPage();

    const analyzeButton = await screen.findByRole("button", { name: "확인 완료하고 분석하기" });
    expect(analyzeButton).toBeDisabled();
    expect(screen.getAllByRole("button", { name: /직접 확인$/ })).toHaveLength(2);
    fireEvent.click(screen.getByRole("radio", { name: "가입 가능" }));
    fireEvent.click(screen.getByRole("radio", { name: "등기 소유자와 직접 계약" }));
    fireEvent.click(screen.getByRole("button", { name: "전세보증 가입 요건 확인 이 값 확인" }));
    fireEvent.click(screen.getByRole("button", { name: "임대·전대 권한 확인 이 값 확인" }));
    expect(analyzeButton).toBeEnabled();
    fireEvent.click(analyzeButton);

    await waitFor(() => expect(submit).toHaveBeenCalledWith({
      schema_version: "1.9.0",
      contract_id: 1001,
      corrections: [
        {
          document_type: "contract",
          field_name: "guarantee_eligibility_confirmed",
          corrected_value: true,
        },
        {
          document_type: "contract",
          field_name: "lessor_sublease_authority_confirmed",
          corrected_value: true,
        },
      ],
    }));
  });

  it("moves a not-stated field to confirmed items through direct confirmation", async () => {
    const contract: DocumentExtractionDto = {
      schema_version: "1.9.0",
      document_id: "DOC-NOT-STATED",
      document_type: "contract",
      warnings: [],
      fields: {
        account_holder: {
          field_name: "account_holder",
          extracted_value: null,
          normalized_value: null,
          user_corrected_value: null,
          verification_status: "unverified",
          confidence: "불확실",
          source_evidence: { page: null, text: null },
          issue_code: "not_stated",
          failure_reason: "문서에 예금주가 기재되어 있지 않습니다.",
        },
      },
    };
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue({
      id: 21,
      status: "completed",
      error: null,
      contract_doc: contract,
      registry_doc: null,
      created_at: "2026-07-21T00:00:00Z",
    });

    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "입금 계좌 예금주 직접 확인" }));
    expect(screen.getByText("확인된 항목 1개")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "확인 완료하고 분석하기" })).toBeEnabled();
  });

  it("sends the user back to upload when extraction cannot be loaded", async () => {
    // 잘못된 문서로 추출이 실패하면 재폴링은 같은 실패만 반환하므로,
    // 복구 경로는 문서를 다시 올리는 것뿐이다.
    vi.spyOn(mvpService, "getLatestExtraction").mockRejectedValue(new Error("network down"));

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("network down");
    fireEvent.click(screen.getByRole("button", { name: "문서 다시 올리기" }));
    expect(await screen.findByText("문서 업로드 화면")).toBeInTheDocument();
  });

  it("renders the empty extraction state", async () => {
    vi.spyOn(mvpService, "getLatestExtraction").mockResolvedValue(emptyExtraction);

    renderPage();

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
    fireEvent.click(screen.getByRole("button", { name: "특약사항 이 값 확인" }));
    fireEvent.change(screen.getByLabelText("입금 계좌 예금주 값"), {
      target: { value: "이정훈" },
    });
    fireEvent.click(screen.getByRole("button", { name: "입금 계좌 예금주 이 값 확인" }));

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
