import type {
  PracticeFinalActionRequestDto,
  PracticeMediaJobDto,
  PracticeAdvanceRequestDto,
  PracticeConversationPageDto,
  PracticeResultResponseDto,
  PracticeScenarioDetailDto,
  PracticeScenarioSummaryDto,
  PracticeSessionDto,
  PracticeTurnRequestDto,
  PracticeTurnResponseDto,
} from "../types/api";
import { apiBlobClient, apiClient } from "./apiClient";

function jsonOptions(method: "POST", body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function createPracticeRequestId(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

export const practiceService = {
  listScenarios: () => apiClient<PracticeScenarioSummaryDto[]>("/api/practice-scenarios"),
  getScenario: (scenarioId: string) =>
    apiClient<PracticeScenarioDetailDto>(`/api/practice-scenarios/${scenarioId}`),
  createSession: (scenarioId: string) =>
    apiClient<PracticeSessionDto>("/api/practice-sessions", jsonOptions("POST", { scenario_id: scenarioId })),
  getSession: (sessionId: string) =>
    apiClient<PracticeSessionDto>(`/api/practice-sessions/${sessionId}`),
  getMessages: (sessionId: string, before?: string, limit = 30) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (before) query.set("before", before);
    return apiClient<PracticeConversationPageDto>(
      `/api/practice-sessions/${sessionId}/messages?${query.toString()}`,
    );
  },
  submitTurn: (sessionId: string, body: PracticeTurnRequestDto) =>
    apiClient<PracticeTurnResponseDto>(
      `/api/practice-sessions/${sessionId}/turns`,
      jsonOptions("POST", body),
    ),
  getMediaJob: (mediaJobId: string) =>
    apiClient<PracticeMediaJobDto>(`/api/practice-media-jobs/${mediaJobId}`),
  getMediaVideo: (videoUrl: string) => apiBlobClient(videoUrl),
  advanceDialogue: (sessionId: string, body: PracticeAdvanceRequestDto) =>
    apiClient<PracticeTurnResponseDto>(
      `/api/practice-sessions/${sessionId}/advance`,
      jsonOptions("POST", body),
    ),
  submitFinalAction: (sessionId: string, body: PracticeFinalActionRequestDto) =>
    apiClient<PracticeTurnResponseDto>(
      `/api/practice-sessions/${sessionId}/final-action`,
      jsonOptions("POST", body),
    ),
  getResult: (sessionId: string) =>
    apiClient<PracticeResultResponseDto>(`/api/practice-sessions/${sessionId}/result`),
};
