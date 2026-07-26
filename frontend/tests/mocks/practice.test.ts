// @vitest-environment jsdom
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { practiceHandlers } from "../../src/mocks/practice";
import { ApiError } from "../../src/services/apiClient";
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
    const messages = await practiceService.getMessages(session.practice_session_id, undefined, 2);
    expect(messages.items).toHaveLength(2);
    expect(messages.items[1].turn_id).toBe("TURN-03");
    expect(messages.has_more).toBe(true);
    const olderMessages = await practiceService.getMessages(
      session.practice_session_id,
      messages.next_cursor!,
      2,
    );
    expect(olderMessages.items.map((item) => item.turn_id)).toEqual(["TURN-01"]);

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
    expect(result.ending_type).toBe("rights_asserted");
    expect(result.action_summary).toHaveLength(3);
    expect(result.official_source_ids.length).toBeGreaterThan(0);
  });

  // 조건을 수용하면 즉시 계약 결정으로 넘어가고, 그 결정이 엔딩을 가른다.
  it.each([
    {
      label: "conditions accepted",
      answers: ["다음 세입자가 들어오는 그 조건이면 괜찮으니 그대로 진행하겠습니다."],
      finalAction: "진행",
      ending: "insufficient_protection",
    },
    {
      label: "transaction held",
      answers: ["다음 세입자가 들어오는 그 조건이면 괜찮으니 그대로 진행하겠습니다."],
      finalAction: "중단",
      ending: "transaction_stopped",
    },
  ] as const)("returns the $label ending report", async ({ answers, finalAction, ending }) => {
    let session = await practiceService.createSession("PRACTICE-DEFERRED-REFUND-001");
    for (let index = 0; index < answers.length; index += 1) {
      const response = await practiceService.submitTurn(session.practice_session_id, {
        request_id: `ending-${ending}-${index}`,
        turn_id: session.current_turn!.turn_id,
        user_answer: answers[index],
        timed_out: false,
        response_time_seconds: 2,
      });
      session = response.session;
    }
    expect(session.current_state).toBe("ACTION-SELECTION");
    await practiceService.submitFinalAction(session.practice_session_id, {
      request_id: `ending-final-${ending}`,
      selected_action: finalAction,
      response_time_seconds: 1,
    });

    const result = (await practiceService.getResult(session.practice_session_id)).result;
    expect(result.ending_type).toBe(ending);
    expect(result.ending_title).toBeTruthy();
    expect(result.practice_phrase).toBeTruthy();
    expect(result.action_summary).toHaveLength(3);
  });

  it("records a timed-out answer and advances to the next turn", async () => {
    const session = await practiceService.createSession("PRACTICE-DEFERRED-REFUND-001");
    const response = await practiceService.submitTurn(session.practice_session_id, {
      request_id: "timeout-request-001",
      turn_id: "TURN-01",
      user_answer: null,
      timed_out: true,
      response_time_seconds: 10,
    });

    expect(response.evaluation?.answer_category).toBe("no_response");
    expect(response.session.current_turn?.turn_id).toBe("TURN-02");
  });

  it("recognizes a clear refund demand even when the wording includes 특약대로", async () => {
    const session = await practiceService.createSession("PRACTICE-DEFERRED-REFUND-001");
    const response = await practiceService.submitTurn(session.practice_session_id, {
      request_id: "clear-refund-demand-001",
      turn_id: "TURN-01",
      user_answer: "특약대로 다음 세입자가 안 들어오게 되더라도 보증금 반환해 주셔야죠.",
      timed_out: false,
      response_time_seconds: 2,
    });

    expect(response.evaluation?.answer_category).toBe("appropriate_check");
    expect(response.session.confirmed_action_ids).toEqual(["PA01"]);
    expect(response.session.current_turn?.turn_id).toBe("TURN-02");
  });

  it("recognizes clear acceptance as avoidance from the canonical rule set", async () => {
    const session = await practiceService.createSession("PRACTICE-DEFERRED-REFUND-001");
    const response = await practiceService.submitTurn(session.practice_session_id, {
      request_id: "clear-acceptance-001",
      turn_id: "TURN-01",
      user_answer: "다음 세입자가 들어오는 그 조건이면 괜찮으니 그대로 진행하겠습니다.",
      timed_out: false,
      response_time_seconds: 2,
    });

    expect(response.evaluation?.answer_category).toBe("avoidance");
    expect(response.session.confirmed_action_ids).toEqual([]);
    // 조건 수용은 즉시 계약 결정 화면으로 간다.
    expect(response.session.current_turn).toBeNull();
    expect(response.session.current_state).toBe("ACTION-SELECTION");
  });

  it.each([
    [
      "오늘 점심은 뭘 먹을까요?",
      "ambiguous_answer",
      "말씀하신 뜻이 분명하지 않은데, 앞서 안내드린 조건대로 진행해도 될까요?",
    ],
    [
      "계약 얘기는 알겠는데 조금 고민됩니다.",
      "partial_check",
      "말씀하신 취지는 알겠지만, 그 부분은 나중에 확인하고 우선 진행하시죠.",
    ],
  ])("returns an in-role reaction for %s and asks again in the same scene", async (answer, category, reaction) => {
    const session = await practiceService.createSession("PRACTICE-DEFERRED-REFUND-001");
    const response = await practiceService.submitTurn(session.practice_session_id, {
      request_id: `reaction-${category}`,
      turn_id: "TURN-01",
      user_answer: answer,
      timed_out: false,
      response_time_seconds: 2,
    });

    expect(response.evaluation?.answer_category).toBe(category);
    expect(response.dialogue_response).toBe(reaction);
    // 부족·애매한 답변에는 같은 장면에서 최대 2회까지 다시 묻는다.
    expect(response.session.current_turn?.turn_id).toBe("TURN-01");
    expect(response.session.confirmed_action_ids).toEqual([]);
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
    const failure = practiceService.listScenarios();
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      name: "ApiError",
      code: "network_error",
      status: 0,
    });
  });
});
