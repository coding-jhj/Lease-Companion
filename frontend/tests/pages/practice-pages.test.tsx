// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PracticeHomePage } from "../../src/pages/practice/PracticeHomePage";
import { PracticeResultPage } from "../../src/pages/practice/PracticeResultPage";
import { PracticeScenarioPage } from "../../src/pages/practice/PracticeScenarioPage";
import { PracticeSessionPage } from "../../src/pages/practice/PracticeSessionPage";
import { practiceService } from "../../src/services/practiceService";
import type {
  PracticeDialogueTurnDto,
  PracticeResultDto,
  PracticeScenarioDetailDto,
  PracticeScenarioSummaryDto,
  PracticeSessionDto,
  PracticeTurnResponseDto,
} from "../../src/types/api";

const scenarioCases = [
  ["PRACTICE-DEFERRED-REFUND-001", "후임 임차인 조건부 보증금 반환", "보증금은 신규 임차인이 입주한 후 반환한다."],
  ["PRACTICE-THIRD-PARTY-PAYMENT-001", "공인중개사 명의 계좌로 가계약금 송금 요구", "중개사 명의 계좌의 수령 권한을 확인한다."],
  ["PRACTICE-PROXY-AUTHORITY-001", "대리인 권한 자료 없는 계약 요구", "위임장과 인감증명서를 계약 전에 확인한다."],
] as const;

function summary(scenarioId: string, title: string): PracticeScenarioSummaryDto {
  return {
    scenario_id: scenarioId,
    scenario_version: "1.0.0",
    title,
    role: scenarioId.includes("DEFERRED") ? "임대인" : "공인중개사",
    difficulty: "기본",
    contract_stage: "서명 전",
    always_show_labels: ["가상 연습", "합성 시나리오"],
  };
}

function dialogueTurn(turnId = "TURN-01", prompt = "계약을 바로 진행하시겠습니까?"): PracticeDialogueTurnDto {
  return { turn_id: turnId, prompt, wait_sequence: [] };
}

function detail(scenarioId: string, title: string, clause: string): PracticeScenarioDetailDto {
  return {
    ...summary(scenarioId, title),
    synthetic_contract: {
      contract_type: "전세",
      signed: false,
      deposit_paid: false,
      property_address: "서울특별시 가온구 연습로 1",
      deposit: 200000000,
      monthly_rent: null,
      contract_payment: 20000000,
      balance_payment: 180000000,
      requested_provisional_payment: 0,
      contract_payment_date: "2026-07-25",
      balance_payment_date: "2026-08-31",
      move_in_date: "2026-08-31",
      start_date: "2026-08-31",
      end_date: "2028-08-30",
      landlord_name: "가상임대인",
      broker_name: "가상중개사",
      is_proxy_contract: scenarioId.includes("PROXY"),
      agent_name: scenarioId.includes("PROXY") ? "가상대리인" : null,
      agent_relationship: scenarioId.includes("PROXY") ? "친족" : null,
      proxy_authority_documents: [],
      account_holder: scenarioId.includes("THIRD-PARTY") ? "가상중개사" : "가상임대인",
      account_number_stored: false,
      registry_issue_date: "2026-07-22",
      registry_property_address: "서울특별시 가온구 연습로 1",
      owner_names: ["가상임대인"],
      is_joint_ownership: false,
      owner_shares: { 가상임대인: "1/1" },
      mortgage_present: false,
      mortgage_maximum_claim: null,
      deposit_return_clause: clause,
      rights_change_clause_present: true,
      special_clauses: [clause],
    },
    initial_turn: dialogueTurn(),
  };
}

function session(overrides: Partial<PracticeSessionDto> = {}): PracticeSessionDto {
  return {
    practice_session_id: "session-001",
    scenario_id: "PRACTICE-DEFERRED-REFUND-001",
    scenario_version: "1.0.0",
    status: "active",
    current_state: "TURN-01",
    current_turn: dialogueTurn(),
    confirmed_action_ids: [],
    selected_action: null,
    allowed_final_actions: ["진행", "추가 확인", "보류", "중단"],
    started_at: "2026-07-22T00:00:00Z",
    completed_at: null,
    ...overrides,
  };
}

function turnResponse(nextSession: PracticeSessionDto, category: "appropriate_check" | "no_response" | "needs_review" = "appropriate_check"): PracticeTurnResponseDto {
  return {
    practice_turn_id: "practice-turn-001",
    attempt_no: 1,
    evaluation: {
      schema_version: "1.9.0",
      turn_id: "TURN-01",
      answer_category: category,
      confirmed_action_ids: category === "appropriate_check" ? ["PA01"] : [],
      next_dialogue_state: nextSession.current_state,
      fallback_reason: category === "needs_review" ? "provider_timeout" : null,
      evidence_text: category === "appropriate_check" ? "자료를 확인하겠습니다." : null,
      verbal_reliance: "not_observed",
    },
    dialogue_response: category === "needs_review" ? "답변을 다시 말씀해 주세요." : "확인 요청을 반영했습니다.",
    session: nextSession,
  };
}

function renderScenario(scenarioId: string) {
  return render(
    <MemoryRouter initialEntries={[`/practice/scenarios/${scenarioId}`]}>
      <Routes>
        <Route path="/practice/scenarios/:scenarioId" element={<PracticeScenarioPage />} />
        <Route path="/practice/sessions/:sessionId" element={<p>대화 세션 진입 완료</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

function renderSession() {
  return render(
    <MemoryRouter initialEntries={["/practice/sessions/session-001"]}>
      <Routes>
        <Route path="/practice/sessions/:sessionId" element={<PracticeSessionPage />} />
        <Route path="/practice/sessions/:sessionId/result" element={<p>결과 화면 이동 완료</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Practice scenario pages", () => {
  it("shows all three approved synthetic scenarios without answer data", async () => {
    vi.spyOn(practiceService, "listScenarios").mockResolvedValue(
      scenarioCases.map(([id, title]) => summary(id, title)),
    );
    render(<MemoryRouter><PracticeHomePage /></MemoryRouter>);

    const list = await screen.findByRole("region", { name: "연습 시나리오 목록" });
    for (const [, title] of scenarioCases) {
      expect(within(list).getByRole("heading", { name: title })).toBeInTheDocument();
    }
    expect(screen.getAllByText("가상 연습")).toHaveLength(3);
    expect(screen.queryByText(/정답표|hidden_confirmation_signals|필수 의미/)).not.toBeInTheDocument();
  });

  it.each(scenarioCases)("renders and starts %s through the common detail page", async (scenarioId, title, clause) => {
    vi.spyOn(practiceService, "getScenario").mockResolvedValue(detail(scenarioId, title, clause));
    const createSession = vi.spyOn(practiceService, "createSession").mockResolvedValue(
      session({ practice_session_id: `session-${scenarioId}` }),
    );
    renderScenario(scenarioId);

    expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByText("서울특별시 가온구 연습로 1")).toBeInTheDocument();
    expect(screen.getByText(clause)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "대화 연습 시작" }));

    await waitFor(() => expect(createSession).toHaveBeenCalledWith(scenarioId));
    expect(await screen.findByText("대화 세션 진입 완료")).toBeInTheDocument();
  });
});

describe("PracticeSessionPage", () => {
  it("restores the current turn, submits an answer, and renders the next turn", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const next = session({ current_state: "TURN-02", current_turn: dialogueTurn("TURN-02", "권한 자료도 필요할까요?"), confirmed_action_ids: ["PA01"] });
    const submit = vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(next));
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: " 자료를 확인하고 보류하겠습니다. " } });
    fireEvent.click(screen.getByRole("button", { name: "답변 보내기" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith("session-001", expect.objectContaining({
      turn_id: "TURN-01",
      user_answer: "자료를 확인하고 보류하겠습니다.",
      timed_out: false,
    })));
    expect(await screen.findByRole("heading", { name: "권한 자료도 필요할까요?" })).toBeInTheDocument();
    expect(screen.getByText("필요한 확인 행동이 전달되었습니다.")).toBeInTheDocument();
  });

  it("submits a timeout without answer text and keeps the same turn", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const submit = vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(session(), "no_response"));
    renderSession();

    fireEvent.click(await screen.findByRole("button", { name: "답변하지 못했어요" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith("session-001", expect.objectContaining({
      turn_id: "TURN-01",
      user_answer: null,
      timed_out: true,
    })));
    expect(screen.getByText("답변하지 못한 턴입니다. 같은 상황에서 다시 답할 수 있습니다.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "계약을 바로 진행하시겠습니까?" })).toBeInTheDocument();
  });

  it("explains a provider review fallback and allows the same turn to be retried", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(session(), "needs_review"));
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "자료를 확인하겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "답변 보내기" }));

    expect(await screen.findByText("답변을 자동으로 평가하지 못했습니다. 같은 턴에서 다시 답해 주세요.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "계약을 바로 진행하시겠습니까?" })).toBeInTheDocument();
    const retryAnswer = screen.getByLabelText("내 답변");
    expect(retryAnswer).toBeEnabled();
    expect(retryAnswer).toHaveValue("");
    fireEvent.change(retryAnswer, { target: { value: "같은 내용을 다시 확인하겠습니다." } });
    expect(screen.getByRole("button", { name: "답변 보내기" })).toBeEnabled();
  });

  it("preserves the typed answer after a network error", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    vi.spyOn(practiceService, "submitTurn").mockRejectedValue(new Error("네트워크 연결을 확인해 주세요."));
    renderSession();

    const answer = await screen.findByLabelText("내 답변");
    fireEvent.change(answer, { target: { value: "권한 자료를 확인하겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "답변 보내기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("네트워크 연결을 확인해 주세요.");
    expect(answer).toHaveValue("권한 자료를 확인하겠습니다.");
    expect(screen.getByRole("button", { name: "답변 보내기" })).toBeEnabled();
  });

  it("submits only an allowed final action and navigates to the result", async () => {
    const actionSession = session({ current_state: "ACTION-SELECTION", current_turn: null, confirmed_action_ids: ["PA01", "PA02"] });
    vi.spyOn(practiceService, "getSession").mockResolvedValue(actionSession);
    const submit = vi.spyOn(practiceService, "submitFinalAction").mockResolvedValue({
      practice_turn_id: "final-turn-001",
      attempt_no: 1,
      evaluation: null,
      dialogue_response: null,
      session: session({ status: "completed", current_state: "DEBRIEF", current_turn: null, selected_action: "보류", completed_at: "2026-07-22T00:10:00Z" }),
    });
    renderSession();

    const finalSection = (await screen.findByRole("heading", { name: "이 계약 상황에서 어떻게 행동하시겠습니까?" })).closest("section")!;
    expect(within(finalSection).getAllByRole("button").map((button) => button.textContent)).toEqual(["진행", "추가 확인", "보류", "중단"]);
    fireEvent.click(within(finalSection).getByRole("button", { name: "보류" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith("session-001", expect.objectContaining({ selected_action: "보류" })));
    expect(await screen.findByText("결과 화면 이동 완료")).toBeInTheDocument();
  });

  it("redirects a restored completed session to its result", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(
      session({ status: "completed", current_state: "DEBRIEF", current_turn: null, selected_action: "보류", completed_at: "2026-07-22T00:10:00Z" }),
    );
    renderSession();
    expect(await screen.findByText("결과 화면 이동 완료")).toBeInTheDocument();
  });
});

describe("PracticeResultPage", () => {
  it("renders the score-free debrief, official source IDs, and replay links", async () => {
    const result: PracticeResultDto = {
      schema_version: "1.9.0",
      session_id: "session-001",
      scenario_id: "PRACTICE-DEFERRED-REFUND-001",
      scenario_version: "1.0.0",
      selected_action: "보류",
      confirmed_action_ids: ["PA01"],
      missed_action_ids: ["PA02"],
      confirmed_actions: ["반환 조건을 확인함"],
      missed_signals: ["구두 약속만으로 진행하지 않기"],
      recommended_phrases: ["반환 조건을 특약에 적어 주세요."],
      next_actions: ["수정된 특약을 다시 확인합니다."],
      official_source_ids: ["SRC-STD-LEASE"],
    };
    vi.spyOn(practiceService, "getResult").mockResolvedValue({ result });
    render(
      <MemoryRouter initialEntries={["/practice/sessions/session-001/result"]}>
        <Routes><Route path="/practice/sessions/:sessionId/result" element={<PracticeResultPage />} /></Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "보류" })).toBeInTheDocument();
    expect(screen.getByText("반환 조건을 확인함")).toBeInTheDocument();
    expect(screen.getByText("구두 약속만으로 진행하지 않기")).toBeInTheDocument();
    expect(screen.getByText("반환 조건을 특약에 적어 주세요.")).toBeInTheDocument();
    expect(screen.getByText("수정된 특약을 다시 확인합니다.")).toBeInTheDocument();
    expect(screen.getByText("SRC-STD-LEASE")).toBeInTheDocument();
    expect(screen.queryByText(/안전 점수|위험 점수|사기 가능성/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "같은 상황 다시 연습" })).toHaveAttribute("href", "/practice/scenarios/PRACTICE-DEFERRED-REFUND-001");
  });
});
