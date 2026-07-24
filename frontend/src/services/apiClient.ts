import type { ApiErrorBody, ApiValidationDetail } from "../types/api";
import { getAccessToken, notifyUnauthorized } from "./authToken";

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly details?: ApiValidationDetail[],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseErrorBody(response: Response): Promise<ApiErrorBody | null> {
  const text = await response.text();
  if (!text.trim()) return null;
  try {
    return JSON.parse(text) as ApiErrorBody;
  } catch {
    return null;
  }
}

async function request(url: string, options: RequestInit): Promise<Response> {
  try {
    return await fetch(url, options);
  } catch {
    throw new ApiError(
      "network_error",
      "서버에 연결할 수 없습니다. Backend 실행 상태를 확인한 뒤 다시 시도해 주세요.",
      0,
    );
  }
}

export async function apiClient<T>(url: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", "Bearer " + token);
  const response = await request(url, { ...options, headers });

  if (!response.ok) {
    if (response.status === 401) notifyUnauthorized();
    const body = await parseErrorBody(response);
    throw new ApiError(
      body?.error?.code ?? (response.status >= 500 ? "server_unavailable" : "http_error"),
      body?.error?.message ?? (
        response.status >= 500
          ? "서버가 응답하지 않습니다. Backend 실행 상태를 확인한 뒤 다시 시도해 주세요."
          : "요청을 처리하지 못했습니다."
      ),
      response.status,
      body?.error?.details,
    );
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  if (!text.trim()) {
    throw new ApiError("invalid_response", "서버에서 빈 응답을 받았습니다. 잠시 후 다시 시도해 주세요.", response.status);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError("invalid_response", "서버 응답 형식이 올바르지 않습니다.", response.status);
  }
}

export async function apiBlobClient(url: string, options?: RequestInit): Promise<Blob> {
  const headers = new Headers(options?.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", "Bearer " + token);
  const response = await request(url, { ...options, headers });

  if (!response.ok) {
    if (response.status === 401) notifyUnauthorized();
    const body = await parseErrorBody(response);
    const message = body?.error?.message ?? (
      response.status >= 500
        ? "미디어 서버가 응답하지 않습니다. Backend 실행 상태를 확인해 주세요."
        : "미디어를 불러오지 못했습니다."
    );
    const code = body?.error?.code ?? (response.status >= 500 ? "server_unavailable" : "http_error");
    throw new ApiError(code, message, response.status);
  }
  return response.blob();
}
