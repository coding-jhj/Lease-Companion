const ACCESS_TOKEN_KEY = "lease-companion.access-token";

export const AUTH_UNAUTHORIZED_EVENT = "lease-companion:unauthorized";

export function getAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function saveAccessToken(token: string): void {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export function notifyUnauthorized(): void {
  clearAccessToken();
  window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
}
