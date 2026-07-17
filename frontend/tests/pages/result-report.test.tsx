// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import analysisRunResultFixture from "../../../data/sample/fixtures/case-001/analysis_run_result.json";
import { ResultReportPage } from "../../src/pages/result-report/ResultReportPage";
import { mvpService } from "../../src/services/mvpService";
import type { AnalysisRunResultDto } from "../../src/types/api";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ResultReportPage", () => {
  it("renders all R01-R10 results and preserves status, urgency, and null judgment_id", async () => {
    vi.spyOn(mvpService, "getAnalysisResult").mockResolvedValue(
      analysisRunResultFixture as AnalysisRunResultDto,
    );

    render(
      <MemoryRouter initialEntries={["/contracts/1001/report"]}>
        <Routes>
          <Route path="/contracts/:contractId/report" element={<ResultReportPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("리포트를 불러오는 중")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "임대인=등기 소유자 이름 일치" })).toBeInTheDocument();
    expect(document.querySelectorAll(".result-card")).toHaveLength(10);

    for (let index = 1; index <= 10; index += 1) {
      expect(screen.getByText("R" + String(index).padStart(2, "0"))).toBeInTheDocument();
    }

    const r01 = screen.getByText("R01").closest("article");
    expect(r01).toHaveTextContent("상태: 불일치");
    expect(r01).toHaveTextContent("시급도: 즉시 확인");
    expect(r01).toHaveTextContent("서명 또는 입금 전에 계약 권한과 관련 서류를 확인하세요.");
    expect(r01).toHaveTextContent("이 결과만으로 사기·위법 여부를 판단할 수 없습니다.");

    for (const ruleId of ["R03", "R04", "R05", "R07", "R10"]) {
      expect(screen.getByText(ruleId).closest("article")).toHaveTextContent("사실 플래그");
    }
  });
});
