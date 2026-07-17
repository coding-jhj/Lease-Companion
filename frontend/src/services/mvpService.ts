import { apiClient } from "./apiClient";
import type {
  AnalysisRunResultDto,
  AuthResponse,
  ChecklistItem,
  ContractSummaryDto,
  CorrectionRequestDto,
  DocumentExtractionDto,
  InputSnapshotDto,
} from "../types/api";
import { mockOnlyMvpRoutes } from "../mocks/mockRoutes";

const jsonHeaders = { "Content-Type": "application/json" };

export const mvpService = {
  authenticate: (mode: "login" | "signup", email: string) =>
    apiClient<AuthResponse>(`/api/auth/${mode}`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ email }),
    }),
  getContracts: () => apiClient<ContractSummaryDto[]>("/api/contracts"),
  createContract: (title: string) =>
    apiClient<ContractSummaryDto>("/api/contracts", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ title }),
    }),
  saveSituation: (contractId: number, contractType: string) =>
    apiClient<{ contract_id: number }>(`/api/contracts/${contractId}/situation`, {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify({ contract_type: contractType }),
    }),
  uploadDocument: (contractId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient<{ document_id: string }>(`/api/contracts/${contractId}/documents`, {
      method: "POST",
      body: formData,
    });
  },
  // 아래 다섯 함수는 OpenAPI 추가 전까지 MSW 전용 경로만 사용한다.
  getExtraction: (contractId: number) =>
    apiClient<DocumentExtractionDto[]>(mockOnlyMvpRoutes.extraction(contractId)),
  submitCorrections: (request: CorrectionRequestDto) =>
    apiClient<CorrectionRequestDto>(mockOnlyMvpRoutes.corrections(request.contract_id), {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(request),
    }),
  confirmExtraction: (contractId: number) =>
    apiClient<InputSnapshotDto>(mockOnlyMvpRoutes.confirmation(contractId), {
      method: "POST",
    }),
  startAnalysis: (contractId: number) =>
    apiClient<{ analysis_run_id: string }>(mockOnlyMvpRoutes.analyses(contractId), {
      method: "POST",
    }),
  getAnalysisResult: (contractId: number) =>
    apiClient<AnalysisRunResultDto>(mockOnlyMvpRoutes.analysisResult(contractId)),
  getChecklist: (contractId: number) =>
    apiClient<ChecklistItem[]>(`/api/contracts/${contractId}/checklist`),
};
