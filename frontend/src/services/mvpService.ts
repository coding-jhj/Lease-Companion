import { apiClient } from "./apiClient";
import type {
  AnalysisRunDetailDto,
  AnalysisRunResultDto,
  AnalysisRunSummaryDto,
  AuthResponse,
  ChecklistItemKind,
  ChecklistItemStateDto,
  ContractSummaryDto,
  CorrectionRequestDto,
  DocumentDto,
  ExtractionStateDto,
  SituationRequestDto,
  SnapshotResponseDto,
  UploadDocumentType,
  UserDto,
} from "../types/api";

const jsonHeaders = { "Content-Type": "application/json" };

export const mvpService = {
  signup: (username: string, email: string, password: string) =>
    apiClient<UserDto>("/api/auth/signup", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ username, email, password }),
    }),
  login: (username: string, password: string) =>
    apiClient<AuthResponse>("/api/auth/login", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ username, password }),
    }),
  getContracts: () => apiClient<ContractSummaryDto[]>("/api/contracts"),
  createContract: (title: string) =>
    apiClient<ContractSummaryDto>("/api/contracts", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ title }),
    }),
  saveSituation: (contractId: number, situation: SituationRequestDto) =>
    apiClient<ContractSummaryDto>(`/api/contracts/${contractId}/situation`, {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify(situation),
    }),
  uploadDocument: (contractId: number, file: File, docType: UploadDocumentType) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", docType);
    return apiClient<DocumentDto>(`/api/contracts/${contractId}/documents`, {
      method: "POST",
      body: formData,
    });
  },
  linkRegistry: (contractId: number, caseId: string) =>
    apiClient<ContractSummaryDto>(`/api/contracts/${contractId}/registry-link`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ case_id: caseId }),
    }),
  startExtraction: (contractId: number) =>
    apiClient<ExtractionStateDto>(`/api/contracts/${contractId}/extractions`, { method: "POST" }),
  getLatestExtraction: (contractId: number) =>
    apiClient<ExtractionStateDto>(`/api/contracts/${contractId}/extractions/latest`),
  submitCorrections: (request: CorrectionRequestDto) =>
    apiClient<ExtractionStateDto>(`/api/contracts/${request.contract_id}/corrections`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(request),
    }),
  confirmExtraction: (contractId: number) =>
    apiClient<SnapshotResponseDto>(`/api/contracts/${contractId}/extractions/confirm`, {
      method: "POST",
    }),
  startAnalysis: (contractId: number) =>
    apiClient<AnalysisRunDetailDto>(`/api/contracts/${contractId}/analysis-runs`, {
      method: "POST",
    }),
  getAnalysisRun: (contractId: number, analysisRunId: string) =>
    apiClient<AnalysisRunDetailDto>(`/api/contracts/${contractId}/analysis-runs/${analysisRunId}`),
  getAnalysisRuns: (contractId: number) =>
    apiClient<AnalysisRunSummaryDto[]>(`/api/contracts/${contractId}/analysis-runs`),
  getAnalysisResult: async (contractId: number, analysisRunId?: string): Promise<AnalysisRunResultDto> => {
    const summaries = analysisRunId ? [] : await apiClient<AnalysisRunSummaryDto[]>(
      `/api/contracts/${contractId}/analysis-runs`,
    );
    const runId = analysisRunId ?? summaries.find((run) => run.status === "completed")?.analysis_run_id;
    if (!runId) throw new Error("완료된 분석 결과가 없습니다.");
    const run = await apiClient<AnalysisRunDetailDto>(
      `/api/contracts/${contractId}/analysis-runs/${runId}`,
    );
    if (!run.result) throw new Error("분석 결과가 아직 준비되지 않았습니다.");
    return run.result;
  },
  getChecklist: (contractId: number) =>
    apiClient<ChecklistItemStateDto[]>(`/api/contracts/${contractId}/checklist-items`),
  updateChecklistItem: (
    contractId: number,
    kind: ChecklistItemKind,
    itemKey: string,
    done: boolean,
  ) => apiClient<ChecklistItemStateDto>(
    `/api/contracts/${contractId}/checklist-items/${kind}/${encodeURIComponent(itemKey)}`,
    { method: "PUT", headers: jsonHeaders, body: JSON.stringify({ done }) },
  ),
};
