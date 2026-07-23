// @vitest-environment jsdom
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { practiceHandlers } from "../../src/mocks/practice";
import { practiceService } from "../../src/services/practiceService";

const server = setupServer(...practiceHandlers);
const nativeFetch = globalThis.fetch;

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  const interceptedFetch = globalThis.fetch;
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const target = typeof input === "string"
      ? input
      : input instanceof URL
        ? input.href
        : input.url;
    return interceptedFetch(new URL(target, window.location.origin), init);
  }) as typeof fetch;
});

afterEach(() => {
  server.resetHandlers();
  window.localStorage.clear();
});

afterAll(() => {
  server.close();
  globalThis.fetch = nativeFetch;
});

describe("Practice MSW handlers", () => {
  it("keeps the list and detail responses free of hidden answer data", async () => {
    const scenarios = await practiceService.listScenarios();
    expect(scenarios).toHaveLength(3);

    for (const summary of scenarios) {
      expect(summary.always_show_labels).toEqual(["가상 연습", "합성 시나리오"]);
      const detail = await practiceService.getScenario(summary.scenario_id);
      expect(detail.initial_turn.turn_id).toBe("TURN-01");
      expect(detail.synthetic_contract.special_clauses.length).toBeGreaterThan(0);
      expect(detail).not.toHaveProperty("answer_key");
      expect(detail).not.toHaveProperty("hidden_confirmation_signals");
      expect(detail).not.toHaveProperty("dialogue_turns");
    }
  });

  it.each([
    "PRACTICE-DEFERRED-REFUND-001",
    "PRACTICE-THIRD-PARTY-PAYMENT-001",
    "PRACTICE-PROXY-AUTHORITY-001",
  ])("runs %s through all turns and returns a saved debrief", async (scenarioId) => {
    let session = await practiceService.createSession(scenarioId);

    for (let index = 0; index < 3; index += 1) {
      expect(session.current_turn?.turn_id).toBe(`TURN-0${index + 1}`);
      const response = await practiceService.submitTurn(session.practice_session_id, {
        request_id: `turn-${scenarioId.slice(-3)}-${index}`,
        turn_id: session.current_turn!.turn_id,
        user_answer: "관련 자료를 확인하고 확인 전에는 보류하겠습니다.",
        timed_out: false,
        response_time_seconds: 2,
      });
      expect(response.evaluation?.answer_category).toBe("appropriate_check");
      session = response.session;
    }

    expect(session.current_state).toBe("ACTION-SELECTION");
    const completed = await practiceService.submitFinalAction(session.practice_session_id, {
      request_id: `final-${scenarioId.slice(-3)}-0`,
      selected_action: "보류",
      response_time_seconds: 1,
    });
    expect(completed.session).toMatchObject({ status: "completed", current_state: "DEBRIEF", selected_action: "보류" });

    const result = (await practiceService.getResult(session.practice_session_id)).result;
    expect(result.scenario_id).toBe(scenarioId);
    expect(result.confirmed_action_ids).toEqual(["PA01", "PA02", "PA03"]);
    expect(result.missed_action_ids).toEqual([]);
    expect(result.official_source_ids.length).toBeGreaterThan(0);
  });

  it("keeps a timed-out answer on the current turn", async () => {
    const session = await practiceService.createSession("PRACTICE-DEFERRED-REFUND-001");
    const response = await practiceService.submitTurn(session.practice_session_id, {
      request_id: "timeout-request-001",
      turn_id: "TURN-01",
      user_answer: null,
      timed_out: true,
      response_time_seconds: 10,
    });

    expect(response.evaluation?.answer_category).toBe("no_response");
    expect(response.session.current_turn?.turn_id).toBe("TURN-01");
  });

  it("advances without confirming the current action", async () => {
    const session = await practiceService.createSession("PRACTICE-DEFERRED-REFUND-001");
    const response = await practiceService.advanceDialogue(session.practice_session_id, {
      request_id: "advance-request-001",
      turn_id: "TURN-01",
      destination: "next_turn",
    });

    expect(response.evaluation).toBeNull();
    expect(response.session.current_turn?.turn_id).toBe("TURN-02");
    expect(response.session.confirmed_action_ids).toEqual([]);
    await expect(practiceService.getSession(session.practice_session_id)).resolves.toMatchObject({
      current_state: "TURN-02",
      confirmed_action_ids: [],
    });

    const actionSelection = await practiceService.advanceDialogue(session.practice_session_id, {
      request_id: "advance-request-002",
      turn_id: "TURN-02",
      destination: "action_selection",
    });
    expect(actionSelection.session).toMatchObject({
      current_state: "ACTION-SELECTION",
      current_turn: null,
      confirmed_action_ids: [],
    });
  });

  it("surfaces a network failure through the shared API client", async () => {
    server.use(http.get("/api/practice-scenarios", () => HttpResponse.error()));
    await expect(practiceService.listScenarios()).rejects.toBeInstanceOf(TypeError);
  });
});
