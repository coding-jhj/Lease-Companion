// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthPage } from "../../src/pages/auth/AuthPage";
import { ContractCreatePage } from "../../src/pages/contract-create/ContractCreatePage";
import { DashboardPage } from "../../src/pages/dashboard/DashboardPage";
import { DocumentUploadPage } from "../../src/pages/document-upload/DocumentUploadPage";
import { ApiError } from "../../src/services/apiClient";
import { mvpService } from "../../src/services/mvpService";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("primary page API errors", () => {
  it("shows a 401 login response without navigating", async () => {
    vi.spyOn(mvpService, "login").mockRejectedValue(new ApiError("unauthorized", "아이디 또는 비밀번호를 확인해 주세요.", 401));
    render(<MemoryRouter><AuthPage mode="login" /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText("아이디"), { target: { value: "tester" } });
    fireEvent.change(screen.getByLabelText("비밀번호"), { target: { value: "password1!" } });
    fireEvent.click(screen.getByRole("button", { name: "로그인하고 시작" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("아이디 또는 비밀번호를 확인해 주세요.");
  });

  it("shows a retryable dashboard state for a 500 response", async () => {
    vi.spyOn(mvpService, "getContracts").mockRejectedValue(new ApiError("internal_error", "계약 목록을 불러오지 못했습니다.", 500));
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);

    expect(await screen.findByText("계약 목록을 불러오지 못했습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });

  it("keeps contract creation retryable for a 422 response", async () => {
    vi.spyOn(mvpService, "createContract").mockRejectedValue(new ApiError("validation_error", "계약 이름을 확인해 주세요.", 422));
    render(<MemoryRouter><ContractCreatePage /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText(/계약 이름/), { target: { value: "테스트 계약" } });
    fireEvent.click(screen.getByRole("button", { name: "다음: 내 상황 알려주기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("계약 이름을 확인해 주세요.");
    expect(screen.getByRole("button", { name: "다음: 내 상황 알려주기" })).toBeEnabled();
  });

  it("shows a 404 upload response and preserves the selected flow", async () => {
    vi.spyOn(mvpService, "uploadDocument").mockRejectedValue(new ApiError("not_found", "계약 건을 찾을 수 없습니다.", 404));
    render(
      <MemoryRouter initialEntries={["/contracts/1001/upload"]}>
        <Routes><Route path="/contracts/:contractId/upload" element={<DocumentUploadPage />} /></Routes>
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText("계약서"), {
      target: { files: [new File(["synthetic"], "contract.txt", { type: "text/plain" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "업로드하고 추출 시작하기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("계약 건을 찾을 수 없습니다.");
    expect(screen.getByRole("button", { name: "업로드하고 추출 시작하기" })).toBeEnabled();
    expect(screen.getByText("이 문서 다시 업로드")).toBeInTheDocument();
  });

  it("rejects unsupported files before an API request", async () => {
    const upload = vi.spyOn(mvpService, "uploadDocument");
    render(
      <MemoryRouter initialEntries={["/contracts/1001/upload"]}>
        <Routes><Route path="/contracts/:contractId/upload" element={<DocumentUploadPage />} /></Routes>
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText("계약서"), {
      target: { files: [new File(["unsafe"], "contract.exe", { type: "application/octet-stream" })] },
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("PDF, JPG, PNG 또는 비식별 데모용 TXT 파일만");
    expect(upload).not.toHaveBeenCalled();
  });
});
