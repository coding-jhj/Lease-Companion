import { http, HttpResponse } from "msw";
import contractExtractionFixture from "../../../data/sample/fixtures/case-001/contract_extraction.json";
import registryExtractionFixture from "../../../data/sample/fixtures/case-001/registry_extraction.json";
import correctionRequestFixture from "../../../data/sample/fixtures/case-001/correction_request.json";
import inputSnapshotFixture from "../../../data/sample/fixtures/case-001/input_snapshot.json";
import analysisRunResultFixture from "../../../data/sample/fixtures/case-001/analysis_run_result.json";
import generationResultFixture from "../../../data/sample/fixtures/case-001/generation_result.json";
import type {
  AnalysisRunDetailDto,
  AnalysisRunResultDto,
  ChecklistItemKind,
  ChecklistItemStateDto,
  ContractSummaryDto,
  CorrectionRequestDto,
  DocumentDto,
  DocumentExtractionDto,
  ExtractionStateDto,
  FeedbackCreateRequestDto,
  FeedbackDto,
  GenerationResultDto,
  InputSnapshotDto,
} from "../types/api";
import { CASE_001_CONTRACT_ID } from "./mockRoutes";

const now = "2026-07-16T00:00:00Z";
const mockContract: ContractSummaryDto = {
  id: CASE_001_CONTRACT_ID,
  title: "CASE-001 전세 계약",
  contract_type: "전세",
  contract_stage: "계약금 입금 전",
  deposit_paid: false,
  signed: false,
  move_in_date: null,
  balance_payment_date: null,
  is_proxy_contract: null,
  registry_case_id: "CASE-001",
  created_at: now,
};

export const case001Fixtures = {
  contract_extraction: contractExtractionFixture as DocumentExtractionDto,
  registry_extraction: registryExtractionFixture as DocumentExtractionDto,
  correction_request: correctionRequestFixture as CorrectionRequestDto,
  input_snapshot: inputSnapshotFixture as InputSnapshotDto,
  analysis_run_result: analysisRunResultFixture as AnalysisRunResultDto,
  generation_result: generationResultFixture as GenerationResultDto,
};

const extraction: ExtractionStateDto = {
  id: 1,
  status: "completed",
  error: null,
  contract_doc: case001Fixtures.contract_extraction,
  registry_doc: case001Fixtures.registry_extraction,
  created_at: now,
};

const analysisDetail: AnalysisRunDetailDto = {
  analysis_run_id: case001Fixtures.analysis_run_result.analysis_run_id,
  input_snapshot_id: case001Fixtures.analysis_run_result.input_snapshot_id,
  status: "completed",
  error: null,
  created_at: now,
  result: case001Fixtures.analysis_run_result,
  generation_result: case001Fixtures.generation_result,
  generation_status: "completed",
  generation_error: null,
};

const documents: DocumentDto[] = [];
const checklist = new Map<string, ChecklistItemStateDto>();
const feedback: FeedbackDto[] = [];

export const handlers = [
  http.post("/api/auth/:mode", async ({ params, request }) => {
    const body = (await request.json()) as { username?: string; email?: string; password?: string };
    if (!body.username || !body.password || (params.mode === "signup" && !body.email)) {
      return HttpResponse.json(
        {
          error: {
            code: "validation_error",
            message: "입력값을 확인해 주세요.",
            details: [{ loc: ["body", "email"], msg: "Field required", type: "missing" }],
          },
        },
        { status: 422 },
      );
    }
    return params.mode === "signup"
      ? HttpResponse.json({ id: 1, username: body.username, email: body.email }, { status: 201 })
      : HttpResponse.json({ access_token: "mock-access-token", token_type: "bearer" });
  }),
  http.get("/api/contracts", () => HttpResponse.json([mockContract])),
  http.post("/api/contracts", async ({ request }) => {
    const body = (await request.json()) as { title?: string };
    if (!body.title) {
      return HttpResponse.json(
        { error: { code: "validation_error", message: "입력값을 확인해 주세요." } },
        { status: 422 },
      );
    }
    return HttpResponse.json({ ...mockContract, title: body.title }, { status: 201 });
  }),
  http.put("/api/contracts/:contractId/situation", async ({ request }) =>
    HttpResponse.json({ ...mockContract, ...await request.json() as object }),
  ),
  http.get("/api/contracts/:contractId/documents", () => HttpResponse.json(documents)),
  http.post("/api/contracts/:contractId/documents", async ({ request }) => {
    const formData = await request.formData();
    const file = formData.get("file") as File;
    const document: DocumentDto = {
      id: documents.length + 1,
      doc_type: String(formData.get("doc_type")) as DocumentDto["doc_type"],
      filename: file.name,
      size_bytes: file.size,
      created_at: now,
    };
    documents.unshift(document);
    return HttpResponse.json(document, { status: 201 });
  }),
  http.post("/api/contracts/:contractId/registry-link", async ({ request }) =>
    HttpResponse.json({ ...mockContract, registry_case_id: ((await request.json()) as { case_id: string }).case_id }),
  ),
  http.post("/api/contracts/:contractId/extractions", () =>
    HttpResponse.json({ ...extraction, status: "pending" }, { status: 202 }),
  ),
  http.get("/api/contracts/:contractId/extractions/latest", () => HttpResponse.json(extraction)),
  http.post("/api/contracts/:contractId/corrections", async ({ request }) => {
    const body = (await request.json()) as CorrectionRequestDto;
    if (body.schema_version !== case001Fixtures.correction_request.schema_version || body.corrections.length === 0) {
      return HttpResponse.json(
        { error: { code: "validation_error", message: "수정 요청 형식을 확인해 주세요." } },
        { status: 422 },
      );
    }
    return HttpResponse.json(extraction);
  }),
  http.post("/api/contracts/:contractId/extractions/confirm", () =>
    HttpResponse.json({ input_snapshot_id: case001Fixtures.input_snapshot.input_snapshot_id, created_at: now }),
  ),
  http.post("/api/contracts/:contractId/analysis-runs", () =>
    HttpResponse.json(analysisDetail, { status: 202 }),
  ),
  http.get("/api/contracts/:contractId/analysis-runs", () =>
    HttpResponse.json([{
      analysis_run_id: analysisDetail.analysis_run_id,
      input_snapshot_id: analysisDetail.input_snapshot_id,
      status: analysisDetail.status,
      created_at: analysisDetail.created_at,
    }]),
  ),
  http.get("/api/contracts/:contractId/analysis-runs/:analysisRunId", () =>
    HttpResponse.json(analysisDetail),
  ),
  http.get("/api/contracts/:contractId/checklist-items", () =>
    HttpResponse.json([...checklist.values()]),
  ),
  http.put("/api/contracts/:contractId/checklist-items/:kind/:itemKey", async ({ params, request }) => {
    const body = (await request.json()) as { done: boolean };
    const item: ChecklistItemStateDto = {
      kind: params.kind as ChecklistItemKind,
      item_key: decodeURIComponent(String(params.itemKey)),
      done: body.done,
      updated_at: now,
    };
    checklist.set(item.kind + ":" + item.item_key, item);
    return HttpResponse.json(item);
  }),
  http.get("/api/contracts/:contractId/feedback", () => HttpResponse.json(feedback)),
  http.post("/api/contracts/:contractId/feedback", async ({ request }) => {
    const body = (await request.json()) as FeedbackCreateRequestDto;
    const item: FeedbackDto = {
      id: feedback.length + 1,
      contract_id: CASE_001_CONTRACT_ID,
      content: body.content,
      rating: body.rating,
      created_at: now,
    };
    feedback.unshift(item);
    return HttpResponse.json(item, { status: 201 });
  }),
];