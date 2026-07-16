import { apiClient } from "./apiClient";
import type {
  AuthResponse,
  ChecklistItem,
  ContractSummary,
  ExtractedField,
  ReportItem,
} from "../types/api";

const jsonHeaders = { "Content-Type": "application/json" };

export const mvpService = {
  authenticate: (mode: "login" | "signup", email: string) =>
    apiClient<AuthResponse>(`/api/auth/${mode}`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ email }),
    }),
  getContracts: () => apiClient<ContractSummary[]>("/api/contracts"),
  createContract: (title: string) =>
    apiClient<ContractSummary>("/api/contracts", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ title }),
    }),
  saveSituation: (contractId: string, contractType: string) =>
    apiClient<{ contractId: string }>(`/api/contracts/${contractId}/situation`, {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify({ contractType }),
    }),
  uploadDocument: (contractId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient<{ documentId: string }>(`/api/contracts/${contractId}/documents`, {
      method: "POST",
      body: formData,
    });
  },
  getExtraction: (contractId: string) =>
    apiClient<ExtractedField[]>(`/api/contracts/${contractId}/extraction`),
  confirmExtraction: (contractId: string, fields: ExtractedField[]) =>
    apiClient<{ inputSnapshotId: string }>(`/api/contracts/${contractId}/extraction`, {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify({ fields }),
    }),
  startAnalysis: (contractId: string) =>
    apiClient<{ analysisRunId: string }>(`/api/contracts/${contractId}/analyses`, {
      method: "POST",
    }),
  getReport: (contractId: string) =>
    apiClient<ReportItem[]>(`/api/contracts/${contractId}/report`),
  getChecklist: (contractId: string) =>
    apiClient<ChecklistItem[]>(`/api/contracts/${contractId}/checklist`),
};
