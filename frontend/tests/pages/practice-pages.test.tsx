// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
    role: "공인중개사",
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
  vi.unstubAllGlobals();
});

function mockDesktopKeyboard(matches: boolean) {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches }));
}

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

    expect(await screen.findByRole("heading", { name: "주택임대차계약서 확인" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "주택임대차계약서" })).toBeInTheDocument();
    expect(screen.getByText("오늘의 미션")).toBeInTheDocument();
    expect(screen.queryByText(title)).not.toBeInTheDocument();
    expect(screen.queryByText("계약을 바로 진행하시겠습니까?")).not.toBeInTheDocument();
    expect(screen.queryByText("가상 연습")).not.toBeInTheDocument();
    expect(screen.queryByText("합성 시나리오")).not.toBeInTheDocument();
    const address = screen.getByText("서울특별시 가온구 연습로 1");
    expect(address).toHaveClass("practice-facts__address");
    expect(address.parentElement).toHaveClass("practice-facts__wide", "practice-facts__wide--aligned");
    expect(address.parentElement).not.toHaveAttribute("style");
    expect(screen.getByText(clause)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "계약서 확인 완료 · 대화 시작" }));

    await waitFor(() => expect(createSession).toHaveBeenCalledWith(scenarioId));
    expect(await screen.findByText("대화 세션 진입 완료")).toBeInTheDocument();
  });
});

describe("PracticeSessionPage", () => {
  beforeEach(() => {
    vi.spyOn(practiceService, "getScenario").mockResolvedValue(
      detail("PRACTICE-DEFERRED-REFUND-001", "보증금 반환 조건 확인", "후임 임차인의 보증금이 입금된 후 반환한다."),
    );
  });

  it("moves the shared broker avatar from speaking to listening", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const view = renderSession();

    expect(await screen.findByText("공인중개사가 말하고 있습니다")).toBeInTheDocument();
    const speakingVideo = view.container.querySelector("video");
    expect(speakingVideo).toHaveAttribute("src", "/practice/avatar/speaking.mp4");

    fireEvent.ended(speakingVideo!);
    expect(await screen.findByText("답변을 듣고 있습니다")).toBeInTheDocument();
    expect(view.container.querySelector("video")).toHaveAttribute("src", "/practice/avatar/listening.mp4");
  });

  it("shows the scenario contract as three navigable pages", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    vi.spyOn(practiceService, "getScenario").mockResolvedValue(
      detail("PRACTICE-DEFERRED-REFUND-001", "보증금 반환 조건 확인", "후임 임차인의 보증금이 입금된 후 반환한다."),
    );
    renderSession();

    expect(await screen.findByRole("heading", { name: "주택임대차계약서" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "보증금 반환 조건 확인하기" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "미션 진행률" })).toHaveAttribute("aria-valuenow", "0");
    expect(screen.getByRole("heading", { name: "1. 기본 계약 내용" })).toBeInTheDocument();
    expect(screen.getByText("1 / 3 페이지")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    expect(screen.getByRole("heading", { name: "2. 일반 계약 조항" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    expect(screen.getByRole("heading", { name: "3. 특약사항" })).toBeInTheDocument();
    expect(screen.getByText("후임 임차인의 보증금이 입금된 후 반환한다.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "확대" }));
    expect(screen.getByRole("button", { name: "축소" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows the broker's first prompt in conversation and toggles the material drawer", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    renderSession();

    fireEvent.click(await screen.findByRole("tab", { name: /대화 내용/ }));
    const conversation = screen.getByRole("tabpanel", { name: "지금까지의 대화" });
    expect(within(conversation).getByText("공인중개사")).toBeInTheDocument();
    expect(within(conversation).getByText("계약을 바로 진행하시겠습니까?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "자료 접기" }));
    expect(screen.queryByRole("tab", { name: "계약서" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "계약서·대화 열기" }));
    expect(screen.getByRole("tab", { name: "계약서" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /대화 내용/ })).toHaveAttribute("aria-selected", "true");
  });

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
    fireEvent.click(screen.getByRole("tab", { name: /대화 내용/ }));
    expect(screen.getByText("자료를 확인하고 보류하겠습니다.")).toBeInTheDocument();
    expect(screen.getAllByText("권한 자료도 필요할까요?")).toHaveLength(2);
    expect(screen.queryByText("확인 요청을 반영했습니다.")).not.toBeInTheDocument();
    expect(screen.queryByText("필요한 확인 행동이 전달되었습니다.")).not.toBeInTheDocument();
  });

  it("submits a non-empty answer with Enter on a PC keyboard", async () => {
    mockDesktopKeyboard(true);
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const submit = vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(session({ current_state: "TURN-02", current_turn: dialogueTurn("TURN-02") })));
    renderSession();

    const textarea = await screen.findByLabelText("내 답변");
    fireEvent.change(textarea, { target: { value: "계약 조건을 확인하겠습니다." } });
    expect(screen.getByText("Enter로 보내기 · Shift+Enter로 줄바꿈")).toHaveClass("practice-answer-shortcut");
    fireEvent.keyDown(textarea, { key: "Enter" });

    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    expect(submit).toHaveBeenCalledWith("session-001", expect.objectContaining({ user_answer: "계약 조건을 확인하겠습니다." }));
  });

  it.each([
    ["Shift+Enter", true, { key: "Enter", shiftKey: true }],
    ["IME composition Enter", true, { key: "Enter", isComposing: true }],
    ["mobile Enter", false, { key: "Enter" }],
  ])("does not submit with %s", async (_label, desktopKeyboard, keyboardEvent) => {
    mockDesktopKeyboard(desktopKeyboard);
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const submit = vi.spyOn(practiceService, "submitTurn");
    renderSession();

    const textarea = await screen.findByLabelText("내 답변");
    fireEvent.change(textarea, { target: { value: "계약 조건을 확인하겠습니다." } });
    fireEvent.keyDown(textarea, keyboardEvent);

    expect(submit).not.toHaveBeenCalled();
  });

  it("does not submit an empty answer or submit twice while a PC request is pending", async () => {
    mockDesktopKeyboard(true);
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const submit = vi.spyOn(practiceService, "submitTurn").mockReturnValue(new Promise(() => {}));
    renderSession();

    const textarea = await screen.findByLabelText("내 답변");
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(submit).not.toHaveBeenCalled();

    fireEvent.change(textarea, { target: { value: "계약 조건을 확인하겠습니다." } });
    fireEvent.keyDown(textarea, { key: "Enter" });
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(submit).toHaveBeenCalledTimes(1);
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
    fireEvent.click(screen.getByRole("tab", { name: /대화 내용/ }));
    expect(screen.getByText("답변하지 못했어요.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "계약을 바로 진행하시겠습니까?" })).toBeInTheDocument();
  });

  it("explains a provider review fallback and allows the same turn to be retried", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(session(), "needs_review"));
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "자료를 확인하겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "답변 보내기" }));

    expect(await screen.findByRole("heading", { name: "계약을 바로 진행하시겠습니까?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /대화 내용/ }));
    expect(screen.getAllByText("계약을 바로 진행하시겠습니까?")).toHaveLength(2);
    expect(screen.queryByText("답변을 다시 말씀해 주세요.")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "AI 연결이 원활하지 않아 답변을 판정하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    );
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

  it("lets the user leave a repeated turn without confirming its action", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const advance = vi.spyOn(practiceService, "advanceDialogue").mockResolvedValue(
      turnResponse(session({ current_state: "TURN-02", current_turn: dialogueTurn("TURN-02", "다음 확인 상황입니다.") })),
    );
    renderSession();

    fireEvent.click(await screen.findByRole("button", { name: "이 확인은 남기고 다음 상황" }));

    await waitFor(() => expect(advance).toHaveBeenCalledWith("session-001", expect.objectContaining({
      turn_id: "TURN-01",
      destination: "next_turn",
    })));
    expect(await screen.findByRole("heading", { name: "다음 확인 상황입니다." })).toBeInTheDocument();
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
  it("renders user-facing official source names without exposing internal IDs", async () => {
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
      official_source_ids: ["SRC-STD-LEASE", "SRC-HTA-LAW", "SRC-UNKNOWN", "SRC-UNKNOWN"],
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
    expect(screen.getByText("주택임대차 표준계약서")).toBeInTheDocument();
    expect(screen.getByText("주택임대차보호법")).toBeInTheDocument();
    expect(screen.getAllByText("공식 자료")).toHaveLength(1);
    expect(screen.queryByText(/^SRC-/)).not.toBeInTheDocument();
    expect(screen.queryByText(/안전 점수|위험 점수|사기 가능성/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "같은 상황 다시 연습" })).toHaveAttribute("href", "/practice/scenarios/PRACTICE-DEFERRED-REFUND-001");
  });
});
