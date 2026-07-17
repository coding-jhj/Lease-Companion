import { describe, expect, it } from "vitest";
import { ApiError } from "../../src/services/apiClient";

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
