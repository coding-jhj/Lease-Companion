// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DocumentUploadCard } from "../../src/features/document-upload/DocumentUploadCard";

describe("DocumentUploadCard", () => {
  it("shows the selected filename, format, size, and upload state", () => {
    render(
      <DocumentUploadCard
        docType="계약서"
        title="계약서"
        description="계약서 설명"
        required
        file={new File([new Uint8Array(2048)], "임대차계약서.pdf", { type: "application/pdf" })}
        status="ready"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("필수 문서")).toBeInTheDocument();
    expect(screen.getByText("임대차계약서.pdf")).toBeInTheDocument();
    expect(screen.getByText("PDF · 2.0킬로바이트")).toBeInTheDocument();
    expect(screen.getByText("업로드 대기")).toBeInTheDocument();
  });

  it("offers a document-level retry after failure", () => {
    const retry = vi.fn();
    render(
      <DocumentUploadCard
        docType="등기사항증명서"
        title="등기사항증명서"
        description="등기 설명"
        file={new File(["registry"], "등기.txt", { type: "text/plain" })}
        status="error"
        error="업로드 연결 실패"
        onSelect={vi.fn()}
        onRetry={retry}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "이 문서 다시 업로드" }));
    expect(retry).toHaveBeenCalledOnce();
    expect(screen.getByRole("alert")).toHaveTextContent("업로드 연결 실패");
  });
});
