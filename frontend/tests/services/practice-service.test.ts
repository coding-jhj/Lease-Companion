// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { createPracticeRequestId, practiceService } from "../../src/services/practiceService";

afterEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe("practiceService", () => {
  it("uses the Practice API paths and JSON request bodies", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({}), { status: 200, headers: { "Content-Type": "application/json" } }),
    );

    await practiceService.listScenarios();
    await practiceService.getScenario("PRACTICE-DEFERRED-REFUND-001");
    await practiceService.createSession("PRACTICE-DEFERRED-REFUND-001");
    await practiceService.getSession("session-001");
    await practiceService.submitTurn("session-001", {
      request_id: "turn-request-001",
      turn_id: "TURN-01",
      user_answer: "계약서 원문을 확인하겠습니다.",
      timed_out: false,
      response_time_seconds: 3,
    });
    await practiceService.advanceDialogue("session-001", {
      request_id: "advance-request-001",
      turn_id: "TURN-01",
      destination: "next_turn",
    });
    await practiceService.submitFinalAction("session-001", {
      request_id: "final-request-001",
      selected_action: "보류",
      response_time_seconds: 1,
    });
    await practiceService.getResult("session-001");

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/practice-scenarios",
      "/api/practice-scenarios/PRACTICE-DEFERRED-REFUND-001",
      "/api/practice-sessions",
      "/api/practice-sessions/session-001",
      "/api/practice-sessions/session-001/turns",
      "/api/practice-sessions/session-001/advance",
      "/api/practice-sessions/session-001/final-action",
      "/api/practice-sessions/session-001/result",
    ]);
    expect(fetchMock.mock.calls[2][1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ scenario_id: "PRACTICE-DEFERRED-REFUND-001" }),
    });
    expect(fetchMock.mock.calls[4][1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({
        request_id: "turn-request-001",
        turn_id: "TURN-01",
        user_answer: "계약서 원문을 확인하겠습니다.",
        timed_out: false,
        response_time_seconds: 3,
      }),
    });
    expect(fetchMock.mock.calls[5][1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({
        request_id: "advance-request-001",
        turn_id: "TURN-01",
        destination: "next_turn",
      }),
    });
    expect(fetchMock.mock.calls[6][1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({
        request_id: "final-request-001",
        selected_action: "보류",
        response_time_seconds: 1,
      }),
    });
    expect(new Headers(fetchMock.mock.calls[2][1]?.headers).get("Content-Type")).toBe("application/json");
  });

  it("creates backend-compatible request IDs", () => {
    expect(createPracticeRequestId("turn")).toMatch(/^turn-[A-Za-z0-9-]{36}$/);
    expect(createPracticeRequestId("final")).toMatch(/^final-[A-Za-z0-9-]{36}$/);
    expect(createPracticeRequestId("advance")).toMatch(/^advance-[A-Za-z0-9-]{36}$/);
  });
});
