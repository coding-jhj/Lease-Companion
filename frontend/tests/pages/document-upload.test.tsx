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
  it("starts extraction with only the required contract document", async () => {
    const upload = vi.spyOn(mvpService, "uploadDocument").mockResolvedValue({
      id: 1,
      doc_type: "계약서",
      filename: "contract.txt",
      size_bytes: 9,
      created_at: "2026-07-20T00:00:00Z",
    });
    const linkRegistry = vi.spyOn(mvpService, "linkRegistry");
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

    fireEvent.change(screen.getByLabelText("계약서"), {
      target: { files: [new File(["synthetic"], "contract.txt", { type: "text/plain" })] },
    });
    expect(screen.getByText("contract.txt")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "업로드하고 다음 단계로" }));

    expect(await screen.findByText("문서 내용 확인 화면")).toBeInTheDocument();
    await waitFor(() => expect(upload).toHaveBeenCalledWith(1001, expect.any(File), "계약서"));
    expect(linkRegistry).not.toHaveBeenCalled();
    expect(startExtraction).toHaveBeenCalledWith(1001);
  });
});
