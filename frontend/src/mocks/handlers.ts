import { delay, http, HttpResponse } from "msw";
import contractExtractionFixture from "../../../data/sample/fixtures/case-001/contract_extraction.json";
import registryExtractionFixture from "../../../data/sample/fixtures/case-001/registry_extraction.json";
import correctionRequestFixture from "../../../data/sample/fixtures/case-001/correction_request.json";
import inputSnapshotFixture from "../../../data/sample/fixtures/case-001/input_snapshot.json";
import analysisRunResultFixture from "../../../data/sample/fixtures/case-001/analysis_run_result.json";
import type {
  AnalysisRunResultDto,
  ChecklistItem,
  ContractSummaryDto,
  CorrectionRequestDto,
  DocumentExtractionDto,
  InputSnapshotDto,
} from "../types/api";
import { CASE_001_CONTRACT_ID, mockOnlyMvpRoutes } from "./mockRoutes";

const mockContract: ContractSummaryDto = {
  contract_id: CASE_001_CONTRACT_ID,
  title: "CASE-001 전세 계약",
  stage: "추출값 확인 전",
  updated_at: "2026-07-16",
};

export const case001Fixtures = {
  contract_extraction: contractExtractionFixture as DocumentExtractionDto,
  registry_extraction: registryExtractionFixture as DocumentExtractionDto,
  correction_request: correctionRequestFixture as CorrectionRequestDto,
  input_snapshot: inputSnapshotFixture as InputSnapshotDto,
  analysis_run_result: analysisRunResultFixture as AnalysisRunResultDto,
};

const checklist: ChecklistItem[] = [
  { id: "check-1", label: "등기사항증명서의 소유자 이름 확인", completed: false },
  { id: "check-2", label: "입금 계좌 명의 확인", completed: false },
  { id: "check-3", label: "계약서와 이체 내역 보관", completed: true },
];

export const handlers = [
  http.post("/api/auth/:mode", async ({ request }) => {
    const body = (await request.json()) as { email?: string };
    if (!body.email) {
      return HttpResponse.json(
        {
          error: {
            code: "validation_error",
            message: "입력값을 확인해 주세요.",
            details: [
              {
                loc: ["body", "email"],
                msg: "Field required",
                type: "missing",
              },
            ],
          },
        },
        { status: 422 },
      );
    }
    return HttpResponse.json({ access_token: "mock-access-token", token_type: "bearer" });
  }),
  http.get("/api/contracts", () => HttpResponse.json([mockContract])),
  http.post("/api/contracts", async ({ request }) => {
    const body = (await request.json()) as { title?: string };
    if (!body.title) {
      return HttpResponse.json(
        {
          error: {
            code: "validation_error",
            message: "입력값을 확인해 주세요.",
            details: [
              {
                loc: ["body", "title"],
                msg: "Field required",
                type: "missing",
              },
            ],
          },
        },
        { status: 422 },
      );
    }
    return HttpResponse.json({ ...mockContract, title: body.title }, { status: 201 });
  }),
  http.put("/api/contracts/:contractId/situation", ({ params }) =>
    HttpResponse.json({ contract_id: Number(params.contractId) }),
  ),
  http.post("/api/contracts/:contractId/documents", () =>
    HttpResponse.json({ document_id: "DOC-1001-CONTRACT" }, { status: 201 }),
  ),
  http.get(mockOnlyMvpRoutes.extraction(CASE_001_CONTRACT_ID), () =>
    HttpResponse.json([
      case001Fixtures.contract_extraction,
      case001Fixtures.registry_extraction,
    ]),
  ),
  http.post(mockOnlyMvpRoutes.corrections(CASE_001_CONTRACT_ID), async ({ request }) => {
    const body = (await request.json()) as CorrectionRequestDto;
    if (body.schema_version !== case001Fixtures.correction_request.schema_version ||
        body.contract_id !== case001Fixtures.correction_request.contract_id ||
        body.corrections.length === 0) {
      return HttpResponse.json(
        { error: { code: "validation_error", message: "수정 요청 형식을 확인해 주세요." } },
        { status: 422 },
      );
    }
    return HttpResponse.json(body);
  }),
  http.post(mockOnlyMvpRoutes.confirmation(CASE_001_CONTRACT_ID), () =>
    HttpResponse.json(case001Fixtures.input_snapshot),
  ),
  http.post(mockOnlyMvpRoutes.analyses(CASE_001_CONTRACT_ID), async () => {
    await delay(500);
    return HttpResponse.json(
      { analysis_run_id: case001Fixtures.analysis_run_result.analysis_run_id },
      { status: 202 },
    );
  }),
  http.get(mockOnlyMvpRoutes.analysisResult(CASE_001_CONTRACT_ID), () =>
    HttpResponse.json(case001Fixtures.analysis_run_result),
  ),
  http.get("/api/contracts/:contractId/checklist", () => HttpResponse.json(checklist)),
];
