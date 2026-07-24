// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentUploadPage } from "../../src/pages/document-upload/DocumentUploadPage";
import { mvpService } from "../../src/services/mvpService";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("DocumentUploadPage", () => {
  it("shows preparation guidance when submitted without a contract document", () => {
    render(
      <MemoryRouter initialEntries={["/contracts/1001/upload"]}>
        <Routes>
          <Route path="/contracts/:contractId/upload" element={<DocumentUploadPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "업로드하고 다음 단계로" }));

    expect(screen.getByRole("alert")).toHaveTextContent("계약서 초안을 올리거나 문서 없이 준비할 내용을 확인해 주세요.");
  });

  it("hides demo registry controls and explains document timing", () => {
    render(
      <MemoryRouter initialEntries={["/contracts/1001/upload"]}>
        <Routes>
          <Route path="/contracts/:contractId/upload" element={<DocumentUploadPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/서명 전에 중개사에게 받아볼 수 있습니다/)).toBeInTheDocument();
    expect(screen.getByText(/지금 없어도 계약서부터 확인할 수 있습니다/)).toBeInTheDocument();
    expect(screen.queryByText(/모의 등기/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/사례 번호/)).not.toBeInTheDocument();
    expect(screen.queryByText(/TXT/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("계약서 사진 또는 파일 올리기")).toHaveAttribute("accept", "application/pdf,image/jpeg,image/png");
    expect(screen.getByLabelText("등기사항증명서 사진 또는 파일 올리기")).toBeInTheDocument();
    expect(screen.getByLabelText("중개대상물 확인설명서 사진 또는 파일 올리기")).toBeInTheDocument();
  });

  it("rejects a TXT file without offering retry, then clears validation when a new file is selected", () => {
    render(
      <MemoryRouter initialEntries={["/contracts/1001/upload"]}>
        <Routes>
          <Route path="/contracts/:contractId/upload" element={<DocumentUploadPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("계약서 사진 또는 파일 올리기"), {
      target: { files: [new File(["synthetic"], "contract.txt", { type: "text/plain" })] },
    });

    expect(screen.getByRole("alert")).toHaveTextContent("PDF, JPG, JPEG 또는 PNG 파일만 업로드할 수 있습니다.");
    expect(screen.queryByRole("button", { name: "이 문서 다시 업로드" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "계약서 새 파일 선택" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("계약서 사진 또는 파일 올리기"), {
      target: { files: [new File(["synthetic"], "contract.pdf", { type: "application/pdf" })] },
    });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("contract.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "계약서 다른 파일 선택" })).toBeInTheDocument();
  });

  it("starts extraction with only the required contract document", async () => {
    const upload = vi.spyOn(mvpService, "uploadDocument").mockResolvedValue({
      id: 1,
      doc_type: "계약서",
      filename: "contract.pdf",
      size_bytes: 9,
      created_at: "2026-07-20T00:00:00Z",
    });
    const startExtraction = vi.spyOn(mvpService, "startExtraction").mockResolvedValue({
      id: 1,
      status: "pending",
      error: null,
      contract_doc: null,
      registry_doc: null,
      created_at: "2026-07-20T00:00:00Z",
    });

    render(
      <MemoryRouter initialEntries={["/contracts/1001/upload"]}>
        <Routes>
          <Route path="/contracts/:contractId/upload" element={<DocumentUploadPage />} />
          <Route path="/contracts/:contractId/review" element={<p>문서 내용 확인 화면</p>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("계약서 사진 또는 파일 올리기"), {
      target: { files: [new File(["synthetic"], "contract.pdf", { type: "application/pdf" })] },
    });
    expect(screen.getByText("contract.pdf")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "업로드하고 다음 단계로" }));

    expect(await screen.findByText("문서 내용 확인 화면")).toBeInTheDocument();
    await waitFor(() => expect(upload).toHaveBeenCalledWith(1001, expect.any(File), "계약서"));
    expect(startExtraction).toHaveBeenCalledWith(1001);
  });
});
