// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "../../src/services/apiClient";
import { AUTH_UNAUTHORIZED_EVENT, getAccessToken, saveAccessToken } from "../../src/services/authToken";

afterEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe("ApiError", () => {
  it("keeps the shared error code, message, HTTP status, and validation details", () => {
    const details = [
      {
        loc: ["body", "password"],
        msg: "String should have at least 8 characters",
        type: "string_too_short",
      },
    ];
    const error = new ApiError("validation_error", "입력값을 확인해 주세요.", 422, details);

    expect(error.name).toBe("ApiError");
    expect(error.code).toBe("validation_error");
    expect(error.message).toBe("입력값을 확인해 주세요.");
    expect(error.status).toBe(422);
    expect(error.details).toEqual(details);
  });
});

describe("apiClient authentication", () => {
  it("adds the stored JWT as a Bearer authorization header", async () => {
    saveAccessToken("test-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await apiClient<{ ok: boolean }>("/api/contracts");

    const options = fetchMock.mock.calls[0][1];
    expect(new Headers(options?.headers).get("Authorization")).toBe("Bearer test-token");
  });

  it("clears the JWT and emits a redirect event on 401", async () => {
    saveAccessToken("expired-token");
    const unauthorized = vi.fn();
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, unauthorized, { once: true });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "unauthorized", message: "로그인이 필요합니다." } }), { status: 401 }),
    );

    await expect(apiClient("/api/contracts")).rejects.toMatchObject({ status: 401 });

    expect(getAccessToken()).toBeNull();
    expect(unauthorized).toHaveBeenCalledOnce();
  });
});
