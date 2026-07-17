import type { ApiErrorBody, ApiValidationDetail } from "../types/api";

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
  const response = await fetch(url, options);

  if (!response.ok) {
    const body = (await response.json()) as ApiErrorBody;
    throw new ApiError(
      body.error.code,
      body.error.message,
      response.status,
      body.error.details,
    );
  }

  return response.json() as Promise<T>;
}
