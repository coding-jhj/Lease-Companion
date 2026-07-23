// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen, within } from "@testing-library/react";
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
    expect(screen.getByLabelText("계약서 사진 또는 파일 올리기")).toHaveAttribute("accept", "application/pdf,image/jpeg,image/png");
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

  it("keeps file selection available but hides retry when validation left no file", () => {
    const view = render(
      <DocumentUploadCard
        docType="계약서"
        title="계약서"
        description="계약서 설명"
        file={null}
        status="error"
        error="PDF 파일만 선택할 수 있습니다."
        onSelect={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(within(view.container).getByRole("button", { name: "계약서 새 파일 선택" })).toBeInTheDocument();
    expect(within(view.container).queryByRole("button", { name: "이 문서 다시 업로드" })).not.toBeInTheDocument();
    expect(within(view.container).getByRole("alert")).toHaveTextContent("PDF 파일만 선택할 수 있습니다.");
  });
});
