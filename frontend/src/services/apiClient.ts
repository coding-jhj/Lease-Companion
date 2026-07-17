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

export async function apiClient<T>(url: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", "Bearer " + token);
  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    if (response.status === 401) notifyUnauthorized();
    const body = (await response.json()) as ApiErrorBody;
    throw new ApiError(
      body.error?.code ?? "http_error",
      body.error?.message ?? "요청을 처리하지 못했습니다.",
      response.status,
      body.error?.details,
    );
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
